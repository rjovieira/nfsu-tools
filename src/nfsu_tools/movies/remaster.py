"""4K Remastering engine for EA MAD movies.

Upscales retro GameCube cutscenes to modern 4K UHD (3840x2160) or 1080p FHD:
- Intelligent aspect ratio correction (GameCube non-square PAR -> 16:9 widescreen or 4:3).
- Automatic cinematic letterbox bar detection and cropping.
- High-fidelity Lanczos edge-preserving upscaling.
- Contrast-Adaptive Sharpening (CAS) for crisp textures and lines without haloing.
- Hardware-accelerated Apple Silicon VideoToolbox (HEVC/H.264) and software (x265/x264/ProRes).
"""

from __future__ import annotations

import platform
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image

from nfsu_tools.common.runner import check_tool_available, run_command
from nfsu_tools.movies.patcher import patch_gamecube_r2_audio


@dataclass(slots=True)
class RemasterConfig:
    """Configuration options for the 4K Remastering pipeline."""

    target_resolution: tuple[int, int] = (3840, 2160)  # 4K UHD standard (16:9)
    aspect_mode: Literal["auto", "16:9", "4:3", "original"] = "auto"
    crop_letterbox: bool = True
    sharpening: Literal["cas", "unsharp", "none"] = "cas"
    sharpening_strength: float = 0.4
    encoder: Literal["auto", "videotoolbox", "libx265", "libx264", "prores"] = "auto"
    video_bitrate: str = "30M"
    audio_bitrate: str = "320k"
    crf: int = 18


def detect_letterbox_geometry(patched_mad: Path) -> tuple[bool, int, int]:
    """Inspect video frames to detect if the video has hardcoded letterbox black bars.

    Returns:
        tuple[bool, int, int]: (is_letterboxed, top_bar_height, bottom_bar_height)
    """
    # Sample at frame 35 to avoid initial fade-ins
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp_img:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(patched_mad),
            "-vf",
            "select=eq(n\\,35)",
            "-vframes",
            "1",
            tmp_img.name,
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            # Fallback to frame 15 if frame 35 fails (short clip)
            cmd[6] = "select=eq(n\\,15)"
            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode != 0:
                return False, 0, 0

        try:
            img = Image.open(tmp_img.name).convert("L")
            arr = np.array(img)
            if arr.shape[0] < 100:
                return False, 0, 0

            row_means = arr.mean(axis=1)
            top = 0
            while top < len(row_means) and row_means[top] < 4:
                top += 1

            bot = len(row_means) - 1
            while bot >= 0 and row_means[bot] < 4:
                bot -= 1

            bottom_bar = len(row_means) - 1 - bot
            active_h = bot - top + 1

            # Classic EA 16:9 letterbox in 512x256 frame has ~32px bars and 192px active height
            if 24 <= top <= 40 and 24 <= bottom_bar <= 40 and 180 <= active_h <= 204:
                return True, top, bottom_bar

            return False, 0, 0
        except Exception:
            return False, 0, 0


def select_best_encoder(preferred: str) -> tuple[str, list[str]]:
    """Determine the optimal FFmpeg video encoder and codec arguments."""
    is_macos = platform.system() == "Darwin"

    if preferred == "prores":
        return "prores_ks", ["-profile:v", "3", "-pix_fmt", "yuv422p10le"]

    if preferred in {"videotoolbox", "auto"}:
        if is_macos:
            return "hevc_videotoolbox", [
                "-b:v",
                "30M",
                "-tag:v",
                "hvc1",
                "-pix_fmt",
                "yuv420p",
            ]
        # On non-macOS, fallback to libx265 or libx264
        return "libx265", ["-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"]

    if preferred == "libx265":
        return "libx265", ["-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"]

    if preferred == "libx264":
        return "libx264", ["-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p"]

    return "libx264", ["-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p"]


def build_filter_chain(
    config: RemasterConfig,
    is_letterboxed: bool,
    top_bar: int,
    bot_bar: int,
) -> str:
    """Build the FFmpeg video filter chain for high quality 4K upscaling."""
    filters: list[str] = []
    target_w, target_h = config.target_resolution

    if config.aspect_mode == "auto":
        if is_letterboxed and config.crop_letterbox:
            # Crop 16:9 active region (e.g. 512x192)
            active_h = 256 - top_bar - bot_bar
            filters.append(f"crop=512:{active_h}:0:{top_bar}")
            # Scale directly to 16:9 target (e.g. 3840x2160)
            filters.append(f"scale={target_w}:{target_h}:flags=lanczos+accurate_rnd")
        else:
            # Full 4:3 canvas (512x256). Scale to 4:3 4K (2880x2160) and pad to 16:9 canvas (3840x2160)
            target_4_3_w = int(target_h * 4 / 3)  # 2880
            pad_x = (target_w - target_4_3_w) // 2
            filters.append(f"scale={target_4_3_w}:{target_h}:flags=lanczos+accurate_rnd")
            filters.append(f"pad={target_w}:{target_h}:{pad_x}:0:black")
    elif config.aspect_mode == "16:9":
        if is_letterboxed and config.crop_letterbox:
            active_h = 256 - top_bar - bot_bar
            filters.append(f"crop=512:{active_h}:0:{top_bar}")
        filters.append(f"scale={target_w}:{target_h}:flags=lanczos+accurate_rnd")
    elif config.aspect_mode == "4:3":
        target_4_3_w = int(target_h * 4 / 3)
        pad_x = (target_w - target_4_3_w) // 2
        filters.append(f"scale={target_4_3_w}:{target_h}:flags=lanczos+accurate_rnd")
        filters.append(f"pad={target_w}:{target_h}:{pad_x}:0:black")
    elif config.aspect_mode == "original":
        filters.append(f"scale={target_w}:{target_h}:flags=lanczos+accurate_rnd")

    # Apply Contrast-Adaptive Sharpening (CAS) or unsharp
    if config.sharpening == "cas":
        strength = max(0.0, min(1.0, config.sharpening_strength))
        filters.append(f"cas={strength:.2f}")
    elif config.sharpening == "unsharp":
        filters.append("unsharp=5:5:0.8:5:5:0.0")

    return ",".join(filters)


def remaster_mad(
    src: Path | str,
    dst: Path | str,
    config: RemasterConfig | None = None,
    overwrite: bool = True,
) -> Path:
    """Remaster an EA MAD movie into a pristine modern 4K video.

    Args:
        src: Input .mad file path.
        dst: Output file path (.mp4, .mkv, .mov).
        config: Optional remaster configuration. Defaults to 4K UHD CAS sharpening.
        overwrite: Overwrite destination file if already present.

    Returns:
        Path: Created output file.
    """
    check_tool_available("ffmpeg")
    src_path = Path(src)
    dst_path = Path(dst)
    cfg = config or RemasterConfig()

    if not src_path.is_file():
        raise FileNotFoundError(f"Input file not found: {src_path}")

    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {dst_path}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="nfsu-remaster-") as tmp_dir:
        patched_mad = Path(tmp_dir) / "patched.mad"
        patch_gamecube_r2_audio(src_path, patched_mad)

        # Detect letterbox geometry
        is_letterboxed, top_bar, bot_bar = detect_letterbox_geometry(patched_mad)

        # Build video filter chain
        vf = build_filter_chain(cfg, is_letterboxed, top_bar, bot_bar)

        # Choose encoder
        encoder, encoder_opts = select_best_encoder(cfg.encoder)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y" if overwrite else "-n",
            "-i",
            str(patched_mad),
            "-vf",
            vf,
            "-c:v",
            encoder,
            *encoder_opts,
            "-c:a",
            "aac",
            "-b:a",
            cfg.audio_bitrate,
        ]

        if dst_path.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            cmd.extend(["-movflags", "+faststart"])

        cmd.append(str(dst_path))

        run_command(cmd)

    return dst_path
