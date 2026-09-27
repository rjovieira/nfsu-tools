import io
import struct

import pytest

from nfsu_tools.common.chunks import iterate_chunks_stream, parse_chunks_bytes


def test_parse_chunks_valid() -> None:
    # Build a simulated EA chunk stream
    chunk1_payload = b"test payload 1"
    chunk1_size = 8 + len(chunk1_payload)
    chunk1 = b"MADk" + struct.pack("<I", chunk1_size) + chunk1_payload

    chunk2_payload = b"audio payload"
    chunk2_size = 8 + len(chunk2_payload)
    chunk2 = b"SCDl" + struct.pack("<I", chunk2_size) + chunk2_payload

    data = chunk1 + chunk2
    chunks = parse_chunks_bytes(data)

    assert len(chunks) == 2
    assert chunks[0].tag == b"MADk"
    assert chunks[0].tag_str == "MADk"
    assert chunks[0].offset == 0
    assert chunks[0].size == chunk1_size
    assert chunks[0].payload_size == len(chunk1_payload)

    assert chunks[1].tag == b"SCDl"
    assert chunks[1].offset == chunk1_size
    assert chunks[1].size == chunk2_size


def test_iterate_chunks_stream() -> None:
    chunk_payload = b"sample stream content"
    chunk_size = 8 + len(chunk_payload)
    data = b"MADm" + struct.pack("<I", chunk_size) + chunk_payload

    stream = io.BytesIO(data)
    chunks = list(iterate_chunks_stream(stream))

    assert len(chunks) == 1
    assert chunks[0].tag == b"MADm"
    assert chunks[0].size == chunk_size


def test_parse_chunks_corrupt_size() -> None:
    # Chunk size less than 8 bytes is illegal in EA chunky format
    corrupt = b"MADk" + struct.pack("<I", 4)
    with pytest.raises(ValueError, match="Invalid chunk size"):
        parse_chunks_bytes(corrupt)


def test_parse_chunks_past_eof() -> None:
    # Chunk size extending past EOF
    corrupt = b"MADk" + struct.pack("<I", 100) + b"short"
    with pytest.raises(ValueError, match="extends past EOF"):
        parse_chunks_bytes(corrupt)
