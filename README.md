# nfsu-tools

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type_checked-mypy-blue.svg)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A high-performance reverse engineering and asset conversion toolkit designed to support the decompilation and modern port of **Need for Speed: Underground** (specifically GameCube `GNDP69` and PC builds).

---

## Highlights

- **EA MAD (Madcow) Video Parser & Inspector**: Deeply dissects IFF-style chunk streams (`MADk`, `MADm`, `MADe`, `SCHl`, `SCCl`, `SCDl`, `SCEl`), video parameters, and PT audio tags.
- **GameCube Big-Endian R2 Audio Fix**: Solves the notorious FFmpeg demuxer crash on GameCube `.mad` files by byte-swapping the 4-byte PowerPC big-endian coded-sample count in ADPCM R2 packets, ensuring 100% audio packet fidelity.
- **Lossless Extraction**: Extract pristine decoded YUV420P frames and PCM audio straight to mathematically lossless H.264 (QP 0) and FLAC.
- **4K UHD Remastering Pipeline**:
  - **Aspect Ratio Intelligence**: Analyzes CRT canvas letterboxing (e.g. 512x256 storing active 16:9 cinematic video in 512x192) and crops hardcoded black bars automatically.
  - **Edge-Preserving Scaling**: Multi-tap Lanczos upscaling combined with AMD Contrast-Adaptive Sharpening (CAS) for crisp vehicle lines without ringing.
  - **Apple Silicon Hardware Acceleration**: Blazing-fast 4K 60fps HEVC encoding using macOS `hevc_videotoolbox` (or cross-platform `libx265`/`libx264`).
- **Concurrent Batch Processing**: Convert or remaster an entire directory of cutscenes in parallel with live Rich terminal progress meters.
- **FAANG-Grade Architecture**: Fully typed (`mypy --strict`), modern PEP 621 packaging (`pyproject.toml`), comprehensive test suite (`pytest`), and lightning-fast linting (`ruff`).

---

## Project Architecture

```
nfsu-tools/
├── pyproject.toml               # PEP 517/518/621 package metadata & tools config
├── README.md
├── src/
│   ├── mad-to-mp4.py            # Backward-compatible script wrapper
│   └── nfsu_tools/              # Core library
│       ├── __init__.py
│       ├── cli.py               # Click + Rich unified command-line interface
│       ├── common/
│       │   ├── chunks.py        # Universal EA Chunky format reader (FourCC + LE size)
│       │   ├── runner.py        # Safe external process runner (FFmpeg/FFprobe)
│       ├── movies/
│       │   ├── constants.py     # Chunk tags (MADk, MADm, SCHl, SCDl, etc.)
│       │   ├── parser.py        # Container & PT audio header TLV parser
│       │   ├── patcher.py       # Big-endian PPC sample count byte-swapper
│       │   ├── decoder.py       # Lossless / high-fidelity MP4/MKV decoder
│       │   ├── remaster.py      # 4K UHD video upscaler & aspect ratio engine
│       │   └── batch.py         # Multi-threaded directory batch processor
└── tests/                       # Unit and integration test suite
    ├── test_chunks.py
    ├── test_parser.py
    ├── test_patcher.py
    └── test_remaster.py
```

---

## Installation & Setup

### Prerequisites

- **Python 3.10+** (managed with `uv`, `pyenv`, or system Python)
- **FFmpeg & FFprobe**:
  ```bash
  # macOS (Homebrew)
  brew install ffmpeg

  # Ubuntu / Debian
  sudo apt-get install ffmpeg
  ```

### Install with `uv` (Recommended)

```bash
git clone https://github.com/rjovieira/nfsu-tools.git
cd nfsu-tools
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## CLI Usage

The package exposes the unified CLI `nfsu` (or `nfsu-tools`):

### 1. Inspect MAD Video Metadata

Inspect chunks, duration, video resolution, audio sample rates, and GameCube endianness:

```bash
nfsu movie inspect /path/to/Movies/01_DAY.mad
```

Example output:

```
                          EA MAD Movie: 01_DAY.mad                          
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property            ┃ Value                                              ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ File Size           │ 7,070,796 bytes (6.74 MB)                          │
│ Total Chunks        │ 1075                                               │
│ Video Resolution    │ 512 x 256 px                                       │
│ Framerate           │ 30.30 fps                                          │
│ Timebase Ticks      │ 0x00215DE0 (2,186,720)                             │
│ Audio Sample Rate   │ 32,028 Hz                                          │
│ Audio Channels      │ Stereo (2)                                         │
│ Audio Total Samples │ 572,806                                            │
│ Audio Duration      │ 17.88 seconds                                      │
│ Platform Endianness │ GameCube Big-Endian (needs R2 audio byte-swapping) │
└─────────────────────┴────────────────────────────────────────────────────┘
```

---

### 2. Lossless Decode to MP4 / MKV

Decode MAD movies preserving bit-perfect YUV420P frames and decoded PCM audio (lossless H.264 + FLAC):

```bash
nfsu movie decode /path/to/Movies/01_DAY.mad -o 01_day.mp4
```

For distribution (CRF 17 + AAC audio):

```bash
nfsu movie decode /path/to/Movies/01_DAY.mad -o 01_day.mp4 --no-lossless
```

---

### 3. 4K UHD Remastering

Upscale retro cutscenes to modern 4K UHD (`3840x2160`) with automatic letterbox cropping and Contrast-Adaptive Sharpening:

```bash
nfsu movie remaster /path/to/Movies/01_DAY.mad -o 01_day_4k.mp4 --target 4k
```

Options:
- `--target [4k|1440p|1080p]`: Target resolution (default: `4k`).
- `--aspect [auto|16:9|4:3|original]`: Aspect ratio handling. `auto` detects cinematic 16:9 cutscenes vs full-frame 4:3 videos.
- `--crop-letterbox / --no-crop-letterbox`: Automatically crops 32px top/bottom black bars from 16:9 cutscenes.
- `--sharpening [cas|unsharp|none]`: Edge enhancement filter (default: `cas`).
- `--sharpen-strength <float>`: CAS strength between `0.0` and `1.0` (default: `0.4`).
- `--encoder [auto|videotoolbox|libx265|libx264|prores]`: Video encoder.

---

### 4. Batch Directory Processing

Convert or remaster an entire directory of `.mad` files concurrently:

```bash
# Remaster all movies to 4K
nfsu movie batch /path/to/Movies -o ./remastered_4k --remaster --target 4k -j 4

# Or lossless decode only
nfsu movie batch /path/to/Movies -o ./decoded_lossless -j 4
```

---

## Deep Dive: The GameCube MAD Quirk

Electronic Arts' **Madcow (`.mad`)** format stores video in macroblock DCT slices and audio in ADPCM chunks. On the GameCube (PowerPC architecture), numeric integers were serialized in Big-Endian.

While FFmpeg's EA demuxer (`electronicarts.c`) reads chunk headers, its `adpcm_ea_r2` decoder expects the 4-byte coded-sample count at the start of each `SCDl` chunk in Little-Endian format (`<I`). When presented with an unpatched GameCube file:

1. FFmpeg reads a big-endian count like `0x00000658` (1,624 samples) as `0x58060000` (1,476,788,224 samples).
2. The packet exceeds valid bounds, throwing `invalid number of samples in packet`.
3. FFmpeg's decode error rate immediately exceeds `0.666`, terminating audio output.

`nfsu-tools` implements a heuristic byte-swapper in `nfsu_tools.movies.patcher`:
```python
# Verifies sample count is physically plausible for the chunk's payload length
be_plausible = 0 < be <= payload_len * 4
le_implausible = le > payload_len * 4 or le == 0
if be_plausible and le_implausible:
    buffer[start : start + 4] = struct.pack("<I", be)
```
This restores 100% of audio packets across every cutscene without dropping a single sample.

---

## Testing & Quality Assurance

Run the test suite with `pytest`:

```bash
pytest -v
```

Run code formatting and style checks:

```bash
ruff check .
mypy src
```

---

## Roadmap

- [x] EA MAD Video Container parser and inspector
- [x] GameCube ADPCM R2 Big-Endian byte-swapping patcher
- [x] Lossless H.264/FLAC decoder pipeline
- [x] 4K UHD Remastering with Lanczos + CAS sharpening & Apple Silicon VideoToolbox
- [x] Concurrent multi-worker batch processing with Rich UI
- [ ] **Car Models (`CARS/` folder)**:
  - Extract and parse `GEOMETRY.BIN` (EAGL 3D mesh chunks, vertex buffers, UVs, normals)
  - Extract and convert `TEXTURES.BIN` (CMPR / DXT GameCube texture blocks -> PNG)
  - Geometry export to OBJ / glTF 2.0 format
- [ ] **Global & Track Assets (`GLOBAL/`, `TRACKS/`)**:
  - Chunky file unpacker and repackage tool
- [ ] **Audio Banks (`SOUND/`)**:
  - EA Sound Bank (`.mus`, `.bnk`) stream extractor

---

## License

MIT License. See [LICENSE](LICENSE) for details.
Need for Speed is a registered trademark of Electronic Arts Inc. This tool is developed for research, preservation, and interoperability purposes.