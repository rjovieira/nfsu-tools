"""Audio patcher for GameCube EA MAD movies.

GameCube (PowerPC 750CL "Gekko") is big-endian. When Electronic Arts compiled MAD movies
for the GameCube version of Need for Speed Underground, the EA ADPCM R2 coded-sample count
at the start of each audio packet (`SCDl` chunk payload) was serialized in big-endian (`>I`).

However, FFmpeg's `adpcm_ea_r2` decoder (and demuxer `electronicarts.c`) expects this 4-byte
sample count in little-endian format (`<I`). Without patching, FFmpeg interprets big-endian
counts as hundreds of millions of samples, triggers `invalid number of samples in packet`,
and aborts audio decoding with error `-1145393733`.

This patcher identifies and byte-swaps the 4-byte sample count in every audio chunk,
allowing FFmpeg to decode both pristine video and 48kHz / 32kHz stereo audio with 100% fidelity.
"""

from __future__ import annotations

import struct
from pathlib import Path

from nfsu_tools.common.chunks import parse_chunks_bytes
from nfsu_tools.movies.constants import AUDIO_DATA_TAGS


def patch_gamecube_r2_bytes(data: bytes | bytearray) -> tuple[bytearray, int]:
    """Patch Big-Endian EA ADPCM R2 sample counts to Little-Endian in memory.

    Returns:
        tuple[bytearray, int]: The modified bytearray buffer and the count of patched chunks.
    """
    buffer = bytearray(data)
    chunks = parse_chunks_bytes(buffer)
    patched_count = 0

    for chunk in chunks:
        if chunk.tag not in AUDIO_DATA_TAGS:
            continue

        payload_start = chunk.payload_offset
        payload_len = chunk.payload_size
        if payload_len < 4:
            continue

        # Extract first 4 bytes as both BE and LE uint32
        be = struct.unpack_from(">I", buffer, payload_start)[0]
        le = struct.unpack_from("<I", buffer, payload_start)[0]

        # In EA ADPCM R2 stereo/mono, sample count is roughly 1-2 samples per byte.
        # A valid sample count cannot exceed payload_len * 4.
        # When written as BE on GameCube, `be` is in range, but `le` evaluates to tens or hundreds of millions.
        be_plausible = 0 < be <= payload_len * 4
        le_implausible = le > payload_len * 4 or le == 0

        if be_plausible and le_implausible:
            buffer[payload_start : payload_start + 4] = struct.pack("<I", be)
            patched_count += 1

    return buffer, patched_count


def patch_gamecube_r2_audio(src: Path | str, dst: Path | str) -> int:
    """Read a GameCube MAD file, apply the endianness patch, and write the result.

    Args:
        src: Path to source GameCube MAD file.
        dst: Path where the patched MAD file should be written.

    Returns:
        int: Number of audio chunks patched.
    """
    src_path = Path(src)
    dst_path = Path(dst)

    data = src_path.read_bytes()
    patched_data, count = patch_gamecube_r2_bytes(data)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(patched_data)
    return count
