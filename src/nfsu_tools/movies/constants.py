"""Constants and FourCC chunk tags for EA MAD video and audio formats."""

# Video container chunk tags
TAG_MAD_HEADER = b"MADk"  # Movie header / stream parameters
TAG_MAD_FRAME = b"MADm"   # Video macroblock data (I/P frames)
TAG_MAD_END = b"MADe"     # Video frame slice end / delimiter

# Audio chunk tags
TAG_SOUND_HEADER = b"SCHl"  # Sound Channel Header (PT stream parameters)
TAG_SOUND_CODEC = b"SCCl"   # Sound Channel Codec description
TAG_SOUND_DATA = b"SCDl"    # Sound Channel Data (ADPCM audio packets)
TAG_SOUND_END = b"SCEl"     # Sound Channel End

# Other known EA audio data tags (for cross-title compatibility)
AUDIO_DATA_TAGS = {
    b"SCDl",
    b"SNDC",
    b"SDEN",
    b"ISNd",
}

# PT Sound Header tag identifiers (Electronic Arts PT Sound System)
PT_TAG_CHANNELS = 0x82      # Number of channels (1=mono, 2=stereo)
PT_TAG_SAMPLE_RATE = 0x84   # Sample rate (Hz)
PT_TAG_NUM_SAMPLES = 0x85   # Total sample count per channel
PT_TAG_CODEC = 0x8C         # Codec ID (0x02 = EA ADPCM R2, etc.)
PT_TAG_END = 0xFF           # End of PT header tags
