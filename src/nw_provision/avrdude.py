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


PAGE0_FROM_END = 64   # the stored image is Page 0 then Page 1 (calibration), the top 64 bytes in bus order


def patch_eeprom(eeprom_data: bytes, page0: bytes) -> bytes:
    """Return a copy of eeprom_data with Page 0 written at EEPROM[length-64:length-32].

    The 32 bytes above it are Page 1, the device's calibration, which
    provisioning leaves as it finds them (NW-Device-Specification, renumbered
    2026-09-23: 0x00-0x3F stored as one image at the top of EEPROM).
    """
    if len(page0) != 32:
        raise ValueError(f"page0 must be 32 bytes, got {len(page0)}")
    if len(eeprom_data) < PAGE0_FROM_END:
        raise ValueError(f"EEPROM data too short: {len(eeprom_data)} bytes")
    return eeprom_data[:-PAGE0_FROM_END] + page0 + eeprom_data[-32:]


def page0_of(eeprom_data: bytes) -> bytes:
    """The Page 0 bytes of a full EEPROM image."""
    return eeprom_data[-PAGE0_FROM_END:-32]
