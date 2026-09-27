"""Universal EA Chunky stream reader and parser.

EA files (MAD movies, EAGL geometry, textures, audio banks) use IFF-style chunks:
- 4-byte ASCII FourCC tag (e.g. b"MADk", b"SCHl", b"SCDl")
- 4-byte little-endian size (uint32, including the 8-byte chunk header)
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True, slots=True)
class Chunk:
    """Represents a discrete EA chunk in a stream or file."""

    offset: int
    tag: bytes
    size: int

    @property
    def tag_str(self) -> str:
        """Decode FourCC as ASCII / Latin-1 for display."""
        return self.tag.decode("latin1", errors="replace")

    @property
    def payload_offset(self) -> int:
        """Offset where payload data starts (after 8-byte header)."""
        return self.offset + 8

    @property
    def payload_size(self) -> int:
        """Length of chunk payload in bytes."""
        return max(0, self.size - 8)


def parse_chunks_bytes(data: bytes | bytearray) -> list[Chunk]:
    """Parse all chunks from an in-memory buffer."""
    chunks: list[Chunk] = []
    pos = 0
    total_len = len(data)

    while pos < total_len:
        if total_len - pos < 8:
            break  # Trailing padding / alignment bytes at EOF

        tag = bytes(data[pos : pos + 4])
        size = struct.unpack_from("<I", data, pos + 4)[0]

        if size < 8:
            raise ValueError(
                f"Invalid chunk size {size} for tag {tag!r} at offset 0x{pos:08X}"
            )

        if pos + size > total_len:
            raise ValueError(
                f"Chunk {tag!r} at 0x{pos:08X} with size {size} extends past EOF "
                f"(buffer length {total_len})"
            )

        chunks.append(Chunk(offset=pos, tag=tag, size=size))
        pos += size

    return chunks


def iterate_chunks_stream(stream: BinaryIO) -> Iterator[Chunk]:
    """Iterate through chunks from an open binary stream without loading the whole file into RAM."""
    header_fmt = "<4sI"
    header_size = struct.calcsize(header_fmt)

    while True:
        pos = stream.tell()
        header = stream.read(header_size)
        if len(header) < header_size:
            break

        tag, size = struct.unpack(header_fmt, header)
        if size < 8:
            raise ValueError(
                f"Invalid chunk size {size} for tag {tag!r} at offset 0x{pos:08X}"
            )

        yield Chunk(offset=pos, tag=tag, size=size)
        # Advance to next chunk
        stream.seek(pos + size)


def parse_chunks(source: Path | str | bytes | bytearray) -> list[Chunk]:
    """Convenience function to parse chunks from either a file path or a buffer."""
    if isinstance(source, (Path, str)):
        return parse_chunks_bytes(Path(source).read_bytes())
    return parse_chunks_bytes(source)
