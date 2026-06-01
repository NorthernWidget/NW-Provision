"""
Thin wrapper around the avrdude command-line tool for EEPROM read/write.

All functions raise AvrdudeError on failure.
"""

import os
import subprocess
import tempfile
from pathlib import Path


class AvrdudeError(Exception):
    pass


def _run(args: list[str]) -> str:
    """Run avrdude; return combined output; raise AvrdudeError on non-zero exit."""
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        raise AvrdudeError(f"avrdude failed (exit {result.returncode}):\n{result.stdout}")
    return result.stdout


def _base_args(programmer: str, part: str, port: str | None) -> list[str]:
    args = ["avrdude", "-c", programmer, "-p", part]
    if port:
        args += ["-P", port]
    return args


def read_eeprom(programmer: str, part: str, port: str | None = None) -> bytes:
    """Read the full EEPROM from a connected board; return raw bytes."""
    fd, tmpfile = tempfile.mkstemp(suffix=".bin")
    os.close(fd)
    try:
        _run(_base_args(programmer, part, port) + ["-U", f"eeprom:r:{tmpfile}:r"])
        return Path(tmpfile).read_bytes()
    finally:
        os.unlink(tmpfile)


def write_eeprom(programmer: str, part: str, data: bytes, port: str | None = None) -> None:
    """Write raw bytes to the full EEPROM of a connected board."""
    fd, tmpfile = tempfile.mkstemp(suffix=".bin")
    try:
        os.write(fd, data)
        os.close(fd)
        _run(_base_args(programmer, part, port) + ["-U", f"eeprom:w:{tmpfile}:r"])
    finally:
        os.unlink(tmpfile)


def patch_eeprom(eeprom_data: bytes, page0: bytes) -> bytes:
    """Return a copy of eeprom_data with the top 32 bytes replaced by page0."""
    if len(page0) != 32:
        raise ValueError(f"page0 must be 32 bytes, got {len(page0)}")
    if len(eeprom_data) < 32:
        raise ValueError(f"EEPROM data too short: {len(eeprom_data)} bytes")
    return eeprom_data[:-32] + page0
