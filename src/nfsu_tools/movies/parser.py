"""EA MAD Movie format inspector and metadata parser."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nfsu_tools.common.chunks import Chunk, parse_chunks
from nfsu_tools.common.runner import ffprobe_json
from nfsu_tools.movies.constants import (
    AUDIO_DATA_TAGS,
    TAG_MAD_HEADER,
    TAG_SOUND_HEADER,
)


@dataclass(slots=True)
class MadkVideoHeader:
    """Parsed fields from MADk movie header chunk."""

    width: int = 0
    height: int = 0
    num_frames: int = 0
    timebase_ticks: int = 0
    fps: float = 30.303


@dataclass(slots=True)
class SchlAudioHeader:
    """Parsed fields from SCHl sound header chunk."""

    sample_rate: int = 0
    channels: int = 0
    total_samples: int = 0
    codec_id: int = 0

    @property
    def duration_seconds(self) -> float:
        if self.sample_rate > 0 and self.total_samples > 0:
            return self.total_samples / self.sample_rate
        return 0.0


@dataclass(slots=True)
class MadMovieInfo:
    """Complete metadata description of an EA MAD movie."""

    path: Path
    file_size: int
    chunks: list[Chunk] = field(default_factory=list)
    chunk_counts: dict[str, int] = field(default_factory=dict)
    video_header: MadkVideoHeader | None = None
    audio_header: SchlAudioHeader | None = None
    has_big_endian_r2_audio: bool = False
    ffprobe_data: dict[str, Any] | None = None

    @property
    def is_gamecube_endian(self) -> bool:
        """True if the audio packets exhibit PowerPC big-endian sample counts."""
        return self.has_big_endian_r2_audio


def parse_madk(chunk_bytes: bytes) -> MadkVideoHeader:
    """Parse MADk header chunk."""
    header = MadkVideoHeader()
    if len(chunk_bytes) < 24:
        return header

    # Bytes 0-3: 'MADk'
    # Bytes 4-7: Size
    # Bytes 8-11: Flags / ID (usually 0)
    # Bytes 12-15: Timebase ticks or timer (e.g. 0x00215de0)
    timebase = struct.unpack_from("<I", chunk_bytes, 12)[0]
    header.timebase_ticks = timebase

    # Bytes 16-17: Width (LE uint16)
    # Bytes 18-19: Height (LE uint16)
    w, h = struct.unpack_from("<HH", chunk_bytes, 16)
    header.width = w
    header.height = h

    # Bytes 20-23: Frame rate info or flags
    # In EA MAD, frame rate is standard 30.303 fps (1000/33 ms)
    header.fps = 1000.0 / 33.0
    return header


def _parse_pt_tags(payload: bytes) -> dict[int, int]:
    """Parse variable-length TLV tags in EA PT audio headers."""
    tags: dict[int, int] = {}
    i = 0
    while i < len(payload):
        tag = payload[i]
        i += 1
        if tag == 0xFF:
            break
        if i >= len(payload):
            break
        length = payload[i]
        i += 1
        if i + length > len(payload):
            break
        val_bytes = payload[i : i + length]
        i += length

        if tag == 0xFD:
            # Sub-block inside PT header (common in GameCube files)
            sub_tags = _parse_pt_tags(val_bytes)
            tags.update(sub_tags)
            continue

        if length == 1:
            tags[tag] = val_bytes[0]
        elif length == 2:
            tags[tag] = struct.unpack(">H", val_bytes)[0]
        elif length == 3:
            tags[tag] = struct.unpack(">I", b"\x00" + val_bytes)[0]
        elif length == 4:
            tags[tag] = struct.unpack(">I", val_bytes)[0]

    return tags


def parse_schl(chunk_bytes: bytes) -> SchlAudioHeader:
    """Parse SCHl sound header chunk using EA PT subheader tag-length structure."""
    header = SchlAudioHeader()
    pt_offset = chunk_bytes.find(b"PT")
    if pt_offset == -1:
        return header

    pos = pt_offset + 4
    # Scan for 0xFD (audio subheader marker)
    while pos < len(chunk_bytes):
        b = chunk_bytes[pos]
        pos += 1
        if b == 0xFF:
            break
        if b == 0xFD:
            # Entered audio subheader
            while pos < len(chunk_bytes):
                sub_tag = chunk_bytes[pos]
                pos += 1
                if sub_tag in (0xFF, 0x8A):
                    break
                if pos >= len(chunk_bytes):
                    break
                sz = chunk_bytes[pos]
                pos += 1
                if pos + sz > len(chunk_bytes):
                    break
                val_bytes = chunk_bytes[pos : pos + sz]
                pos += sz

                val = int.from_bytes(val_bytes, byteorder="big", signed=False)

                if sub_tag == 0x82:
                    header.channels = val
                elif sub_tag == 0x84:
                    header.sample_rate = val
                elif sub_tag == 0x85:
                    header.total_samples = val
                elif sub_tag == 0x8C:
                    header.codec_id = val
            break

    return header


def inspect_mad(path: Path | str, run_ffprobe: bool = True) -> MadMovieInfo:
    """Inspect and extract structured metadata from an EA MAD movie file."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    data = file_path.read_bytes()
    chunks = parse_chunks(data)

    counts: dict[str, int] = {}
    for c in chunks:
        counts[c.tag_str] = counts.get(c.tag_str, 0) + 1

    video_header: MadkVideoHeader | None = None
    audio_header: SchlAudioHeader | None = None
    has_be_audio = False

    for c in chunks:
        if c.tag == TAG_MAD_HEADER and video_header is None:
            chunk_data = data[c.offset : c.offset + c.size]
            video_header = parse_madk(chunk_data)
        elif c.tag == TAG_SOUND_HEADER and audio_header is None:
            chunk_data = data[c.offset : c.offset + c.size]
            audio_header = parse_schl(chunk_data)
        elif c.tag in AUDIO_DATA_TAGS and not has_be_audio:
            payload = data[c.payload_offset : c.payload_offset + c.payload_size]
            if len(payload) >= 4:
                be = struct.unpack_from(">I", payload, 0)[0]
                le = struct.unpack_from("<I", payload, 0)[0]
                if 0 < be <= len(payload) * 4 and (le > len(payload) * 4 or le == 0):
                    has_be_audio = True

    ffprobe_data: dict[str, Any] | None = None
    if run_ffprobe:
        try:
            ffprobe_data = ffprobe_json(file_path)
        except Exception:
            ffprobe_data = None

    return MadMovieInfo(
        path=file_path,
        file_size=len(data),
        chunks=chunks,
        chunk_counts=counts,
        video_header=video_header,
        audio_header=audio_header,
        has_big_endian_r2_audio=has_be_audio,
        ffprobe_data=ffprobe_data,
    )
