import struct

from nfsu_tools.movies.patcher import patch_gamecube_r2_bytes


def test_patch_gamecube_r2_bytes_normal_packet() -> None:
    # 1000 samples in Big-Endian for a 1200-byte SCDl payload
    payload_len = 1200
    be_count = 1008  # Multiple of 28
    payload = bytearray(struct.pack(">I", be_count) + b"\x00" * (payload_len - 4))
    chunk = b"SCDl" + struct.pack("<I", len(payload) + 8) + payload

    patched_data, count = patch_gamecube_r2_bytes(chunk)
    assert count == 1

    # Check that bytes 8..12 are now little-endian 1008
    unpacked_le = struct.unpack_from("<I", patched_data, 8)[0]
    assert unpacked_le == be_count


def test_patch_gamecube_r2_bytes_partial_last_packet() -> None:
    # Trailing packet with non-multiple of 28 samples (e.g. 1046 samples)
    payload_len = 1244
    be_count = 1046
    payload = bytearray(struct.pack(">I", be_count) + b"\x00" * (payload_len - 4))
    chunk = b"SCDl" + struct.pack("<I", len(payload) + 8) + payload

    patched_data, count = patch_gamecube_r2_bytes(chunk)
    assert count == 1
    unpacked_le = struct.unpack_from("<I", patched_data, 8)[0]
    assert unpacked_le == be_count


def test_patch_gamecube_r2_preserves_native_little_endian() -> None:
    # If the file is already little-endian (e.g. PC version of NFSU), do not mutate
    payload_len = 1200
    le_count = 1008
    payload = bytearray(struct.pack("<I", le_count) + b"\x00" * (payload_len - 4))
    chunk = b"SCDl" + struct.pack("<I", len(payload) + 8) + payload

    patched_data, count = patch_gamecube_r2_bytes(chunk)
    assert count == 0  # No chunks modified
    assert patched_data == chunk


def test_patch_ignores_non_audio_chunks() -> None:
    # MADm video chunk should not be modified
    payload = bytearray(struct.pack(">I", 1000) + b"\x00" * 100)
    chunk = b"MADm" + struct.pack("<I", len(payload) + 8) + payload

    patched_data, count = patch_gamecube_r2_bytes(chunk)
    assert count == 0
    assert patched_data == chunk
