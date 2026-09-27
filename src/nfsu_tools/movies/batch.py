"""Batch conversion and remastering pipeline for directories of MAD movies."""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from nfsu_tools.movies.decoder import decode_mad
from nfsu_tools.movies.remaster import RemasterConfig, remaster_mad


@dataclass(slots=True)
class BatchResult:
    """Outcome of a single movie conversion in a batch job."""

    src_path: Path
    dst_path: Path
    success: bool
    duration_seconds: float
    error_message: str | None = None
    file_size_bytes: int = 0


def batch_process_movies(
    input_dir: Path | str,
    output_dir: Path | str,
    remaster: bool = False,
    remaster_config: RemasterConfig | None = None,
    lossless: bool = True,
    output_ext: str = ".mp4",
    max_workers: int = 4,
    console: Console | None = None,
) -> list[BatchResult]:
    """Batch convert all .mad files in an input directory.

    Args:
        input_dir: Directory containing .mad files.
        output_dir: Destination directory for converted MP4/MKV files.
        remaster: If True, applies 4K remastering pipeline. If False, decodes.
        remaster_config: Config options for remastering.
        lossless: Used if remaster is False (lossless H.264/FLAC).
        output_ext: Extension for output files (.mp4, .mkv, .mov).
        max_workers: Parallel concurrency limit.
        console: Optional Rich console for printing status.

    Returns:
        list[BatchResult]: Summary results of every processed file.
    """
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    mad_files = sorted(in_path.glob("*.mad"))
    if not mad_files:
        # Also try case-insensitive
        mad_files = sorted([p for p in in_path.iterdir() if p.suffix.lower() == ".mad"])

    if not mad_files:
        return []

    c = console or Console()
    results: list[BatchResult] = []

    def process_one(src_file: Path) -> BatchResult:
        dst_file = out_path / f"{src_file.stem}{output_ext}"
        t0 = time.time()
        try:
            if remaster:
                remaster_mad(src_file, dst_file, config=remaster_config, overwrite=True)
            else:
                decode_mad(src_file, dst_file, lossless=lossless, overwrite=True)
            elapsed = time.time() - t0
            size = dst_file.stat().st_size if dst_file.exists() else 0
            return BatchResult(
                src_path=src_file,
                dst_path=dst_file,
                success=True,
                duration_seconds=elapsed,
                file_size_bytes=size,
            )
        except Exception as exc:
            elapsed = time.time() - t0
            return BatchResult(
                src_path=src_file,
                dst_path=dst_file,
                success=False,
                duration_seconds=elapsed,
                error_message=str(exc),
            )

    action_label = "Remastering (4K)" if remaster else "Decoding"
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=c,
    ) as progress:
        task_id = progress.add_task(f"{action_label} movies...", total=len(mad_files))

        # Use ThreadPoolExecutor so FFmpeg spawns subprocesses efficiently
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(process_one, f): f for f in mad_files}
            for future in concurrent.futures.as_completed(future_to_file):
                res = future.result()
                results.append(res)
                progress.advance(task_id)

    # Sort results by filename
    results.sort(key=lambda r: r.src_path.name)
    return results
