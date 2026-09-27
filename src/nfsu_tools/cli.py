"""Unified command-line interface for nfsu-tools."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nfsu_tools import __version__
from nfsu_tools.movies.batch import batch_process_movies
from nfsu_tools.movies.decoder import decode_mad
from nfsu_tools.movies.parser import inspect_mad
from nfsu_tools.movies.patcher import patch_gamecube_r2_audio
from nfsu_tools.movies.remaster import RemasterConfig, remaster_mad

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-v", "--version", message="nfsu-tools version %(version)s")
def main() -> None:
    """Need for Speed Underground (GameCube / PC) reverse engineering & asset toolkit."""


@main.group()
def movie() -> None:
    """EA MAD (Madcow) movie tools: inspect, patch, decode, and 4K remaster."""


@movie.command("inspect")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def movie_inspect(input_file: Path) -> None:
    """Inspect chunks, video headers, and audio parameters of an EA MAD file."""
    try:
        info = inspect_mad(input_file)
    except Exception as exc:
        console.print(f"[bold red]Inspection failed:[/] {exc}")
        sys.exit(1)

    table = Table(title=f"EA MAD Movie: {input_file.name}", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("File Size", f"{info.file_size:,} bytes ({info.file_size / (1024*1024):.2f} MB)")
    table.add_row("Total Chunks", str(len(info.chunks)))

    if info.video_header:
        vh = info.video_header
        table.add_row("Video Resolution", f"{vh.width} x {vh.height} px")
        table.add_row("Framerate", f"{vh.fps:.2f} fps")
        table.add_row("Timebase Ticks", f"0x{vh.timebase_ticks:08X} ({vh.timebase_ticks:,})")

    if info.audio_header:
        ah = info.audio_header
        ch_str = "Stereo (2)" if ah.channels == 2 else f"Mono ({ah.channels})"
        table.add_row("Audio Sample Rate", f"{ah.sample_rate:,} Hz")
        table.add_row("Audio Channels", ch_str)
        table.add_row("Audio Total Samples", f"{ah.total_samples:,}")
        table.add_row("Audio Duration", f"{ah.duration_seconds:.2f} seconds")

    endian_status = (
        "[bold yellow]GameCube Big-Endian (needs R2 audio byte-swapping)[/]"
        if info.has_big_endian_r2_audio
        else "[bold green]Standard Little-Endian (PC native)[/]"
    )
    table.add_row("Platform Endianness", endian_status)

    console.print(table)

    # Chunk summary breakdown
    chunk_table = Table(title="Chunk Tag Breakdown", show_header=True, header_style="bold magenta")
    chunk_table.add_column("Tag", style="bold")
    chunk_table.add_column("Description")
    chunk_table.add_column("Count", justify="right")

    tag_descriptions = {
        "MADk": "Movie header / stream params",
        "MADm": "Video frame macroblocks (I/P frames)",
        "MADe": "Video frame delimiter / slice end",
        "SCHl": "Sound channel header (PT properties)",
        "SCCl": "Sound channel codec configuration",
        "SCDl": "Sound channel data (ADPCM packets)",
        "SCEl": "Sound channel end delimiter",
    }

    for tag, count in sorted(info.chunk_counts.items()):
        desc = tag_descriptions.get(tag, "EA data chunk")
        chunk_table.add_row(repr(tag), desc, str(count))

    console.print(chunk_table)


@movie.command("patch")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", "output_file", type=click.Path(dir_okay=False, path_type=Path), required=True, help="Destination patched .mad file.")
def movie_patch(input_file: Path, output_file: Path) -> None:
    """Patch GameCube Big-Endian EA ADPCM R2 sample counts for standard FFmpeg compatibility."""
    try:
        count = patch_gamecube_r2_audio(input_file, output_file)
        console.print(f"[bold green]Successfully patched {count} audio chunks.[/] Saved to: [cyan]{output_file}[/]")
    except Exception as exc:
        console.print(f"[bold red]Patching failed:[/] {exc}")
        sys.exit(1)


@movie.command("decode")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", "output_file", type=click.Path(dir_okay=False, path_type=Path), required=True, help="Output file (.mp4, .mkv, .mov).")
@click.option("--lossless/--no-lossless", default=True, help="Lossless H.264 (QP 0) + FLAC vs high-quality CRF 17 + AAC.")
def movie_decode(input_file: Path, output_file: Path, lossless: bool) -> None:
    """Decode an EA MAD file to standard MP4/MKV video with pristine audio."""
    with console.status(f"[bold cyan]Decoding {input_file.name}...[/]"):
        try:
            res = decode_mad(input_file, output_file, lossless=lossless, overwrite=True)
            size_mb = res.stat().st_size / (1024 * 1024)
            mode = "Lossless H.264 + FLAC" if lossless else "High-Quality H.264 + AAC"
            console.print(f"[bold green]Decoded successfully:[/] [cyan]{res}[/] ({size_mb:.2f} MB, mode: {mode})")
        except Exception as exc:
            console.print(f"[bold red]Decoding failed:[/] {exc}")
            sys.exit(1)


@movie.command("remaster")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", "output_file", type=click.Path(dir_okay=False, path_type=Path), required=True, help="Output file (.mp4, .mov).")
@click.option("--target", type=click.Choice(["4k", "1440p", "1080p"], case_sensitive=False), default="4k", help="Target resolution standard.")
@click.option("--aspect", type=click.Choice(["auto", "16:9", "4:3", "original"], case_sensitive=False), default="auto", help="Aspect ratio handling mode.")
@click.option("--crop-letterbox/--no-crop-letterbox", default=True, help="Auto-crop hardcoded letterbox bars on 16:9 FMVs.")
@click.option("--sharpening", type=click.Choice(["cas", "unsharp", "none"], case_sensitive=False), default="cas", help="Sharpening filter.")
@click.option("--sharpen-strength", type=float, default=0.4, help="Contrast-adaptive sharpening strength (0.0 to 1.0).")
@click.option("--encoder", type=click.Choice(["auto", "videotoolbox", "libx265", "libx264", "prores"], case_sensitive=False), default="auto", help="Video encoder.")
def movie_remaster(
    input_file: Path,
    output_file: Path,
    target: str,
    aspect: str,
    crop_letterbox: bool,
    sharpening: str,
    sharpen_strength: float,
    encoder: str,
) -> None:
    """Remaster a retro MAD video to modern 4K/1080p with edge-preserving scaling and CAS sharpening."""
    res_map = {
        "4k": (3840, 2160),
        "1440p": (2560, 1440),
        "1080p": (1920, 1080),
    }
    target_res = res_map[target.lower()]
    config = RemasterConfig(
        target_resolution=target_res,
        aspect_mode=aspect.lower(),  # type: ignore[arg-type]
        crop_letterbox=crop_letterbox,
        sharpening=sharpening.lower(),  # type: ignore[arg-type]
        sharpening_strength=sharpen_strength,
        encoder=encoder.lower(),  # type: ignore[arg-type]
    )

    with console.status(f"[bold cyan]Remastering {input_file.name} to {target.upper()}...[/]"):
        try:
            res = remaster_mad(input_file, output_file, config=config, overwrite=True)
            size_mb = res.stat().st_size / (1024 * 1024)
            console.print(
                Panel.fit(
                    f"[bold green]Remaster Complete![/]\n"
                    f"File: [cyan]{res}[/]\n"
                    f"Resolution: [bold]{target_res[0]}x{target_res[1]}[/]\n"
                    f"Size: [bold]{size_mb:.2f} MB[/]\n"
                    f"Aspect Mode: [bold]{aspect}[/]\n"
                    f"Sharpening: [bold]{sharpening} ({sharpen_strength})[/]",
                    title="4K Remaster Pipeline",
                    border_style="green",
                )
            )
        except Exception as exc:
            console.print(f"[bold red]Remaster failed:[/] {exc}")
            sys.exit(1)


@movie.command("batch")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(file_okay=False, path_type=Path), required=True, help="Destination directory.")
@click.option("--remaster/--decode-only", default=False, help="Remaster to 4K or decode to lossless source resolution.")
@click.option("--target", type=click.Choice(["4k", "1440p", "1080p"], case_sensitive=False), default="4k", help="Target resolution if remastering.")
@click.option("-j", "--jobs", default=4, type=int, help="Concurrent worker count.")
def movie_batch(
    input_dir: Path,
    output_dir: Path,
    remaster: bool,
    target: str,
    jobs: int,
) -> None:
    """Batch convert or remaster an entire directory of EA MAD movies."""
    res_map = {
        "4k": (3840, 2160),
        "1440p": (2560, 1440),
        "1080p": (1920, 1080),
    }
    config = RemasterConfig(target_resolution=res_map[target.lower()]) if remaster else None

    console.print(f"[bold cyan]Starting batch processing on {input_dir}...[/]")
    results = batch_process_movies(
        input_dir=input_dir,
        output_dir=output_dir,
        remaster=remaster,
        remaster_config=config,
        max_workers=jobs,
        console=console,
    )

    if not results:
        console.print("[yellow]No .mad movie files found in input directory.[/]")
        return

    table = Table(title="Batch Processing Summary", show_header=True, header_style="bold green")
    table.add_column("File", style="bold")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    table.add_column("Output Size", justify="right")

    success_count = sum(1 for r in results if r.success)
    total_size = sum(r.file_size_bytes for r in results)

    for r in results:
        status = "[bold green]OK[/]" if r.success else f"[bold red]FAILED:[/] {r.error_message}"
        size_str = f"{r.file_size_bytes / (1024*1024):.2f} MB" if r.success else "-"
        table.add_row(r.src_path.name, status, f"{r.duration_seconds:.1f}s", size_str)

    console.print(table)
    console.print(
        f"[bold]Done:[/] {success_count}/{len(results)} files converted successfully "
        f"({total_size / (1024*1024):.2f} MB total)."
    )


if __name__ == "__main__":
    main()
