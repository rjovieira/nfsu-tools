#!/usr/bin/env python3
"""Compatibility script for decoding EA MAD movies to MP4.

This script delegates to the modern nfsu_tools engine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to sys.path so it works without explicit pip install
src_root = Path(__file__).resolve().parent
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from nfsu_tools.movies.decoder import decode_mad  # noqa: E402
from nfsu_tools.movies.parser import inspect_mad  # noqa: E402
from nfsu_tools.movies.remaster import RemasterConfig, remaster_mad  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Inspect, decode, and remaster Need for Speed Underground (.MAD) movies."
    )
    sub = p.add_subparsers(dest="command", required=True)

    # inspect
    s = sub.add_parser("inspect", help="Inspect EA MAD chunks, video, and audio parameters")
    s.add_argument("input", type=Path, help="Path to input .mad file")

    # decode
    d = sub.add_parser("decode", help="Lossless or high-quality decode of MAD -> MP4")
    d.add_argument("input", type=Path, help="Path to input .mad file")
    d.add_argument("output", type=Path, help="Path to output .mp4/.mkv file")
    d.add_argument(
        "--high-quality",
        action="store_true",
        help="Use CRF 17 + AAC instead of lossless QP 0 + FLAC",
    )

    # remaster
    r = sub.add_parser("remaster", help="Remaster retro MAD cutscene to 4K UHD")
    r.add_argument("input", type=Path, help="Path to input .mad file")
    r.add_argument("output", type=Path, help="Path to output .mp4 file")
    r.add_argument(
        "--target",
        choices=["4k", "1440p", "1080p"],
        default="4k",
        help="Target output resolution (default: 4k)",
    )
    r.add_argument(
        "--aspect",
        choices=["auto", "16:9", "4:3", "original"],
        default="auto",
        help="Aspect ratio handling mode (default: auto)",
    )

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        input_path = args.input.resolve()
        if not input_path.is_file():
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            return 1

        if args.command == "inspect":
            info = inspect_mad(input_path)
            print(f"File:       {info.path.name}")
            print(f"Size:       {info.file_size:,} bytes")
            print(f"Chunks:     {len(info.chunks)}")
            if info.video_header:
                print(f"Video:      {info.video_header.width}x{info.video_header.height} @ {info.video_header.fps:.2f} fps")
            if info.audio_header:
                print(f"Audio:      {info.audio_header.sample_rate} Hz, {info.audio_header.channels} ch, {info.audio_header.duration_seconds:.2f}s")
            print(f"Endianness: {'GameCube Big-Endian (ADPCM R2 patch required)' if info.has_big_endian_r2_audio else 'Standard Little-Endian'}")
            print("\nChunk breakdown:")
            for tag, count in sorted(info.chunk_counts.items()):
                print(f"  {tag!r:8}: {count:5}")

        elif args.command == "decode":
            lossless = not args.high_quality
            out = decode_mad(input_path, args.output, lossless=lossless, overwrite=True)
            print(f"Successfully decoded to: {out}")

        elif args.command == "remaster":
            res_map = {"4k": (3840, 2160), "1440p": (2560, 1440), "1080p": (1920, 1080)}
            cfg = RemasterConfig(target_resolution=res_map[args.target], aspect_mode=args.aspect)
            out = remaster_mad(input_path, args.output, config=cfg, overwrite=True)
            print(f"Successfully remastered ({args.target.upper()}) to: {out}")

        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
