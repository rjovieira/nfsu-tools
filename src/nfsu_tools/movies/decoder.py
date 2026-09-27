"""EA MAD (Madcow) Movie decoder.

Decodes MAD video and EA ADPCM R2 audio to standard modern containers (MP4, MKV, MOV).
Supports mathematically lossless extraction of decoded YUV420P frames and PCM audio,
or high-fidelity distribution formats.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from nfsu_tools.common.runner import check_tool_available, run_command
from nfsu_tools.movies.patcher import patch_gamecube_r2_audio


def decode_mad(
    src: Path | str,
    dst: Path | str,
    lossless: bool = True,
    video_codec: str | None = None,
    audio_codec: str | None = None,
    overwrite: bool = True,
) -> Path:
    """Decode an EA MAD movie to MP4/MKV.

    Args:
        src: Input .mad file path.
        dst: Output video file path (.mp4, .mkv, .mov).
        lossless: If True, uses mathematically lossless H.264 (QP 0) and FLAC audio.
                 If False, uses high-fidelity H.264 (CRF 17) and AAC (256k).
        video_codec: Optional override for video codec (e.g. 'libx264', 'h264_videotoolbox').
        audio_codec: Optional override for audio codec (e.g. 'flac', 'aac', 'pcm_s16le').
        overwrite: Whether to overwrite dst if it exists.

    Returns:
        Path: The created output file path.
    """
    check_tool_available("ffmpeg")
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.is_file():
        raise FileNotFoundError(f"Input file not found: {src_path}")

    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {dst_path}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="nfsu-mad-") as tmp_dir:
        patched_mad = Path(tmp_dir) / "patched_input.mad"
        patch_gamecube_r2_audio(src_path, patched_mad)

        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y" if overwrite else "-n",
            "-i",
            str(patched_mad),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
        ]

        if lossless:
            vcodec = video_codec or "libx264"
            acodec = audio_codec or "flac"
            cmd.extend([
                "-c:v",
                vcodec,
                "-qp",
                "0",
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                acodec,
            ])
        else:
            vcodec = video_codec or "libx264"
            acodec = audio_codec or "aac"
            cmd.extend([
                "-c:v",
                vcodec,
                "-crf",
                "17",
                "-preset",
                "slow",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                acodec,
                "-b:a",
                "256k",
            ])

        # If MP4/MOV container, add faststart flag
        if dst_path.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            cmd.extend(["-movflags", "+faststart"])

        cmd.append(str(dst_path))

        run_command(cmd)

    return dst_path
