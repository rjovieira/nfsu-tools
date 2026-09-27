"""External process runner for multimedia tools (FFmpeg, FFprobe)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class ToolNotFoundError(RuntimeError):
    """Raised when an external CLI executable is missing from PATH."""


class ProcessExecutionError(RuntimeError):
    """Raised when an external command exits with a non-zero status."""

    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        msg = (
            f"Command {cmd[0]!r} failed with exit code {returncode}.\n"
            f"Command line: {' '.join(cmd)}\n"
            f"Error output:\n{stderr.strip() or stdout.strip()}"
        )
        super().__init__(msg)


def check_tool_available(name: str) -> str:
    """Verify tool exists on PATH and return its absolute location."""
    path = shutil.which(name)
    if not path:
        raise ToolNotFoundError(
            f"Required executable {name!r} not found on PATH. "
            "Please install it (e.g. `brew install ffmpeg`) and ensure it is available."
        )
    return path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command, capturing output safely."""
    check_tool_available(cmd[0])
    try:
        return subprocess.run(
            cmd,
            check=check,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ProcessExecutionError(
            cmd=cmd,
            returncode=exc.returncode,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
        ) from exc


def ffprobe_json(file_path: Path | str) -> dict[str, Any]:
    """Execute ffprobe and return parsed JSON metadata."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    proc = run_command(cmd)
    try:
        return json.loads(proc.stdout)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to decode ffprobe output: {exc}\n{proc.stdout}") from exc
