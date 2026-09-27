import struct

from nfsu_tools.movies.parser import parse_madk, parse_schl


def test_parse_madk_header() -> None:
    # Build simulated MADk chunk
    # Bytes 0-3: 'MADk', 4-7: Size (32), 8-11: 0, 12-15: Timebase (0x00215de0)
    # 16-17: width=512, 18-19: height=256, 20-23: flags
    raw = (
        b"MADk"
        + struct.pack("<I", 32)
        + b"\x00\x00\x00\x00"
        + struct.pack("<I", 0x00215DE0)
        + struct.pack("<HH", 512, 256)
        + b"\x02\x01\x01\x00"
        + b"\x00" * 8
    )

    vh = parse_madk(raw)
    assert vh.width == 512
    assert vh.height == 256
    assert vh.timebase_ticks == 0x00215DE0
    assert abs(vh.fps - 30.303) < 0.01


def test_parse_schl_header() -> None:
    # Build simulated SCHl chunk with EA PT subheader
    # PT subheader: 0xFD marker, tags 0x82 (2 ch), 0x84 (48000 Hz), 0x85 (96000 samples)
    sub = (
        bytes([0x82, 1, 2])  # 2 channels
        + bytes([0x84, 3, 0x00, 0xBB, 0x80])  # 48000 Hz
        + bytes([0x85, 3, 0x01, 0x77, 0x00])  # 96000 samples
        + bytes([0x8C, 1, 4])  # Codec 4
        + bytes([0xFF])
    )
    raw = (
        b"SCHl"
        + struct.pack("<I", 40)
        + b"PT\x00\x00"
        + b"\x00\x00\x00\x00"
        + bytes([0xFD])
        + sub
    )

    ah = parse_schl(raw)
    assert ah.channels == 2
    assert ah.sample_rate == 48000
    assert ah.total_samples == 96000
    assert ah.codec_id == 4
    assert ah.duration_seconds == 2.0
