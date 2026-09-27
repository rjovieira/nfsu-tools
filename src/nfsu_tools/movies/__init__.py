"""EA MAD (Madcow) Movie format tools: inspection, patching, decoding, and 4K remastering."""

from nfsu_tools.movies.decoder import decode_mad
from nfsu_tools.movies.parser import MadMovieInfo, inspect_mad
from nfsu_tools.movies.patcher import patch_gamecube_r2_audio
from nfsu_tools.movies.remaster import RemasterConfig, remaster_mad

__all__ = [
    "MadMovieInfo",
    "RemasterConfig",
    "decode_mad",
    "inspect_mad",
    "patch_gamecube_r2_audio",
    "remaster_mad",
]
