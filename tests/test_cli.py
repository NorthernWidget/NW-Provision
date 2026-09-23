import csv

import pytest
from click.testing import CliRunner

from nw_provision.cli import main


def make_registry(tmp_path, units=None):
    (tmp_path / "units").mkdir()
    if units:
        for device, rows in units.items():
            path = tmp_path / "units" / f"{device.lower()}.csv"
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["board_type", "group_id", "individual_id",
                            "firmware_id", "hw_version", "location", "notes"])
                for row in rows:
                    w.writerow(row)
    return tmp_path


# --- write --dry-run ---

def test_write_dry_run_no_registry():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write",
        "--device", "Margay",
        "--hw-version", "3.0",
        "--id", "1",
        "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "dry run" in result.output
    assert "Margay" in result.output


def test_write_dry_run_board_type_in_output():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "3.0",
        "--id", "1", "--dry-run",
    ])
    assert "0x4D03" in result.output  # board_type_high=0x4D, hw_major=3


def test_write_dry_run_haar_board_type():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Haar", "--hw-version", "0.1",
        "--id", "1", "--dry-run",
    ])
    assert "0x4800" in result.output  # board_type_high=0x48, hw_major=0


def test_write_dry_run_group_hex():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Walrus", "--hw-version", "0.2",
        "--group", "0x4E57", "--id", "5", "--dry-run",
    ])
    assert result.exit_code == 0
    assert "0x4E57" in result.output


# --- --id auto with registry ---

def test_write_auto_id_dry_run(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "", ""],
    ]})
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "3.0",
        "--id", "auto", "--registry", str(reg),
        "--dry-run",
    ], input="y\n")
    assert result.exit_code == 0, result.output
    assert "0x0002" in result.output  # next after 0x0001


def test_write_auto_id_requires_registry():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "3.0",
        "--id", "auto", "--dry-run",
    ])
    assert result.exit_code != 0
    assert "registry" in result.output.lower()


# --- --location and --notes written to registry ---

def test_location_notes_written_to_registry(tmp_path):
    reg = make_registry(tmp_path, units={"Walrus": []})
    runner = CliRunner()

    from unittest.mock import patch, MagicMock

    ok_result = MagicMock()
    ok_result.returncode = 0
    ok_result.stdout = "avrdude: done"

    def fake_run_all(args, **kwargs):
        u_arg = next((a for a in args if a.startswith("eeprom:")), None)
        if u_arg and ":r:" in u_arg:
            outfile = u_arg.split(":")[2]
            from nw_provision.page0 import build_page0
            page0 = build_page0("Walrus", hw_major=0, hw_minor=2, fw_patch=0,
                                 group_id=0, unique_id=1, board_type=0x5700)
            data = bytearray(256)  # ATtiny1634 has 256 B EEPROM
            data[-64:-32] = page0
            with open(outfile, "wb") as f:
                f.write(bytes(data))
        return ok_result

    with patch("nw_provision.avrdude.subprocess.run", side_effect=fake_run_all):
        result = runner.invoke(main, [
            "write", "--device", "Walrus", "--hw-version", "0.2",
            "--id", "1", "--registry", str(reg),
            "--programmer", "usbasp",
            "--location", "Iowa City",
            "--notes", "bench test",
        ])

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(open(reg / "units" / "walrus.csv")))
    assert len(rows) == 1
    assert rows[0]["location"] == "Iowa City"
    assert rows[0]["notes"] == "bench test"


# --- list subcommand ---

def test_list_shows_units(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "Iowa", "bench"],
        ["0x4D03", "0x4E57", "0x0002", "0x0000", "3.0.0", "Alaska", ""],
    ]})
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--device", "Margay", "--registry", str(reg)])
    assert result.exit_code == 0, result.output
    assert "0x0001" in result.output
    assert "0x0002" in result.output
    assert "Iowa" in result.output
    assert "2 units" in result.output
    assert "0x0003" in result.output  # next ID


def test_list_empty(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": []})
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--device", "Margay", "--registry", str(reg)])
    assert result.exit_code == 0
    assert "No units found" in result.output


def test_list_board_type_filter(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D02", "0x4E57", "0x0001", "0x0000", "2.0.0", "", ""],
        ["0x4D03", "0x4E57", "0x0002", "0x0000", "3.0.0", "", ""],
    ]})
    runner = CliRunner()
    result = runner.invoke(main, [
        "list", "--device", "Margay", "--registry", str(reg), "--board-type", "0x4D03",
    ])
    assert result.exit_code == 0
    assert "0x0002" in result.output
    assert "0x0001" not in result.output


def test_list_requires_registry():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--device", "Margay"])
    assert result.exit_code != 0


# --- missing --programmer without --dry-run ---

def test_write_requires_programmer_without_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "3.0", "--id", "1",
    ])
    assert result.exit_code != 0
    assert "programmer" in result.output.lower()


# --- Page 1 (calibration) beside Page 0 ---

def fake_eeprom_board(initial: bytes):
    """A subprocess.run stand-in that behaves as a board with `initial` in its EEPROM.

    eeprom:r: hands the current image to avrdude's output file; eeprom:w: takes
    the input file as the new image. Returns (side_effect, state); state["eeprom"]
    is the image after each write.
    """
    from unittest.mock import MagicMock
    state = {"eeprom": bytes(initial), "writes": 0}
    ok = MagicMock()
    ok.returncode = 0
    ok.stdout = "avrdude: done"

    def run(args, **kwargs):
        u_arg = next((a for a in args if a.startswith("eeprom:")), None)
        if u_arg and ":r:" in u_arg:
            with open(u_arg.split(":")[2], "wb") as f:
                f.write(state["eeprom"])
        elif u_arg and ":w:" in u_arg:
            with open(u_arg.split(":")[2], "rb") as f:
                state["eeprom"] = f.read()
            state["writes"] += 1
        return ok
    return run, state


def test_write_dry_run_margay_prints_page1():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "3.0", "--id", "1", "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "0x20  D0 07 0D CF 5B 3B 0A 2B" in result.output   # divider 2000; A
    assert "Battery divider:     2.000" in result.output
    assert "Steinhart-Hart A:    0.003354016" in result.output
    assert "Battery low:         3.30 V" in result.output
    assert "Battery warning:     50 %" in result.output


def test_write_dry_run_margay_model_0_divider():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "0.0", "--id", "1", "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "Battery divider:     9.000" in result.output


def test_write_dry_run_margay_unknown_model_needs_no_page1():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "4.0", "--id", "1", "--dry-run",
    ])
    assert result.exit_code != 0
    assert "unknown Margay model 4" in result.output
    assert "--no-page1" in result.output


def test_write_dry_run_no_page1_flag():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Margay", "--hw-version", "4.0", "--id", "1",
        "--dry-run", "--no-page1",
    ])
    assert result.exit_code == 0, result.output
    assert "left as found (--no-page1)" in result.output
    assert "Battery divider" not in result.output


def test_write_dry_run_okapi_blank_page1():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Okapi", "--hw-version", "1.0", "--id", "1", "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "0x20  FF FF FF FF FF FF FF FF" in result.output
    assert "blank (all 0xFF)" in result.output


def test_write_dry_run_sensor_has_no_page1():
    runner = CliRunner()
    result = runner.invoke(main, [
        "write", "--device", "Apis", "--hw-version", "0.1", "--id", "1", "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "left as found (a sensor's firmware owns its calibration)" in result.output
    assert "0x20 " not in result.output


def test_write_margay_writes_both_pages_and_verifies():
    from unittest.mock import patch
    from nw_provision.page1 import build_margay_page1

    initial = bytes([0x5A]) * 4096            # ATmega1284P; stale content everywhere
    run, state = fake_eeprom_board(initial)
    runner = CliRunner()
    with patch("nw_provision.avrdude.subprocess.run", side_effect=run):
        result = runner.invoke(main, [
            "write", "--device", "Margay", "--hw-version", "3.0", "--id", "1",
            "--programmer", "usbasp",
        ])
    assert result.exit_code == 0, result.output
    assert state["writes"] == 1
    written = state["eeprom"]
    assert written[-32:] == build_margay_page1("3.0")
    assert written[-64:-32][0] == 0x01 and written[-64:-32][1:7] == b"Margay"
    assert written[:-64] == initial[:-64]     # nothing below the stored image touched
    assert "Page 0 and Page 1 verified" in result.output


def test_write_margay_no_page1_leaves_it_as_found():
    from unittest.mock import patch

    initial = bytes(4064) + bytes(range(32))  # a distinctive Page 1
    run, state = fake_eeprom_board(initial)
    runner = CliRunner()
    with patch("nw_provision.avrdude.subprocess.run", side_effect=run):
        result = runner.invoke(main, [
            "write", "--device", "Margay", "--hw-version", "3.0", "--id", "1",
            "--programmer", "usbasp", "--no-page1",
        ])
    assert result.exit_code == 0, result.output
    assert state["eeprom"][-32:] == bytes(range(32))
    assert "Page 0 verified on device." in result.output


def test_write_sensor_leaves_page1_as_found():
    from unittest.mock import patch

    zero = bytes(range(0xA0, 0xC0))           # what Apis firmware might have stored
    initial = bytes(256 - 32) + zero          # ATtiny1634: 256 B
    run, state = fake_eeprom_board(initial)
    runner = CliRunner()
    with patch("nw_provision.avrdude.subprocess.run", side_effect=run):
        result = runner.invoke(main, [
            "write", "--device", "Apis", "--hw-version", "0.1", "--id", "1",
            "--programmer", "usbasp",
        ])
    assert result.exit_code == 0, result.output
    assert state["writes"] == 1
    assert state["eeprom"][-32:] == zero
    assert state["eeprom"][-64:-32][1:5] == b"Apis"


def test_write_page1_readback_mismatch_fails():
    from unittest.mock import MagicMock, patch
    from nw_provision.page0 import build_page0

    # A board whose reads always return a valid Page 0 but a blank Page 1
    page0 = build_page0("Margay", 3, 0, 0, 0, 1, 0x4D03)
    stuck = bytes(4032) + page0 + b"\xFF" * 32
    ok = MagicMock(); ok.returncode = 0; ok.stdout = ""

    def run(args, **kwargs):
        u_arg = next((a for a in args if a.startswith("eeprom:")), None)
        if u_arg and ":r:" in u_arg:
            with open(u_arg.split(":")[2], "wb") as f:
                f.write(stuck)
        return ok

    runner = CliRunner()
    with patch("nw_provision.avrdude.subprocess.run", side_effect=run):
        result = runner.invoke(main, [
            "write", "--device", "Margay", "--hw-version", "3.0", "--id", "1",
            "--programmer", "usbasp",
        ])
    assert result.exit_code == 1
    assert "VERIFY FAIL: Page 1" in result.output

