import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from nw_provision.avrdude import AvrdudeError, patch_eeprom, read_eeprom, write_eeprom


# --- patch_eeprom (pure function) ---

def test_patch_replaces_top_32():
    eeprom = bytes(range(256))
    page0 = bytes([0xAB] * 32)
    result = patch_eeprom(eeprom, page0)
    assert result[-32:] == page0

def test_patch_preserves_lower_bytes():
    eeprom = bytes(range(256))
    page0 = bytes([0xAB] * 32)
    result = patch_eeprom(eeprom, page0)
    assert result[:-32] == eeprom[:-32]

def test_patch_total_length_unchanged():
    eeprom = bytes(1024)
    page0 = bytes(32)
    assert len(patch_eeprom(eeprom, page0)) == 1024

def test_patch_rejects_wrong_page0_size():
    with pytest.raises(ValueError, match="32 bytes"):
        patch_eeprom(bytes(256), bytes(31))

def test_patch_rejects_short_eeprom():
    with pytest.raises(ValueError, match="too short"):
        patch_eeprom(bytes(16), bytes(32))


# --- read_eeprom / write_eeprom (subprocess mocked) ---

def _make_completed(returncode=0, stdout="avrdude: done"):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    return r


def test_read_eeprom_calls_avrdude(tmp_path):
    fake_eeprom = bytes(range(256))

    def fake_run(args, **kwargs):
        # find the output file path from the -U argument and write fake data there
        u_arg = next(a for a in args if a.startswith("eeprom:r:"))
        outfile = u_arg.split(":")[2]
        with open(outfile, "wb") as f:
            f.write(fake_eeprom)
        return _make_completed()

    with patch("nw_provision.avrdude.subprocess.run", side_effect=fake_run):
        result = read_eeprom("usbasp", "m1284p")

    assert result == fake_eeprom


def test_read_eeprom_raises_on_failure():
    with patch("nw_provision.avrdude.subprocess.run", return_value=_make_completed(returncode=1)):
        with pytest.raises(AvrdudeError):
            read_eeprom("usbasp", "m1284p")


def test_write_eeprom_passes_data_to_avrdude():
    written = {}

    def fake_run(args, **kwargs):
        u_arg = next(a for a in args if a.startswith("eeprom:w:"))
        infile = u_arg.split(":")[2]
        with open(infile, "rb") as f:
            written["data"] = f.read()
        return _make_completed()

    payload = bytes(range(64))
    with patch("nw_provision.avrdude.subprocess.run", side_effect=fake_run):
        write_eeprom("usbasp", "m1284p", payload)

    assert written["data"] == payload


def test_write_eeprom_raises_on_failure():
    with patch("nw_provision.avrdude.subprocess.run", return_value=_make_completed(returncode=1)):
        with pytest.raises(AvrdudeError):
            write_eeprom("usbasp", "m1284p", bytes(32))


def test_port_included_in_args():
    seen_args = {}

    def fake_run(args, **kwargs):
        seen_args["args"] = args
        # write dummy file for read path
        u_arg = next((a for a in args if a.startswith("eeprom:r:")), None)
        if u_arg:
            outfile = u_arg.split(":")[2]
            open(outfile, "wb").close()
        return _make_completed()

    with patch("nw_provision.avrdude.subprocess.run", side_effect=fake_run):
        read_eeprom("avrisp2", "m328p", port="/dev/ttyUSB0")

    assert "-P" in seen_args["args"]
    assert "/dev/ttyUSB0" in seen_args["args"]


def test_no_port_omits_flag():
    seen_args = {}

    def fake_run(args, **kwargs):
        seen_args["args"] = args
        u_arg = next((a for a in args if a.startswith("eeprom:r:")), None)
        if u_arg:
            outfile = u_arg.split(":")[2]
            open(outfile, "wb").close()
        return _make_completed()

    with patch("nw_provision.avrdude.subprocess.run", side_effect=fake_run):
        read_eeprom("usbasp", "m1284p", port=None)

    assert "-P" not in seen_args["args"]
