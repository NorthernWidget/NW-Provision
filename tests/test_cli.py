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

    fake_eeprom = bytes(1024)
    ok_result = MagicMock()
    ok_result.returncode = 0
    ok_result.stdout = "avrdude: done"

    def fake_run(args, **kwargs):
        u_arg = next((a for a in args if "eeprom" in a), None)
        if u_arg and ":r:" in u_arg:
            outfile = u_arg.split(":")[2]
            with open(outfile, "wb") as f:
                f.write(fake_eeprom)
        elif u_arg and ":r:" in u_arg:
            pass
        return ok_result

    def fake_run_all(args, **kwargs):
        u_arg = next((a for a in args if a.startswith("eeprom:")), None)
        if u_arg and ":r:" in u_arg:
            outfile = u_arg.split(":")[2]
            from nw_provision.page0 import build_page0
            page0 = build_page0("Walrus", hw_major=0, hw_minor=2, fw_patch=0,
                                 group_id=0, unique_id=1, board_type=0x5700)
            data = bytearray(1024)
            data[-32:] = page0
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
