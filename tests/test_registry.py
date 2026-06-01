import csv
from pathlib import Path

import pytest

from nw_provision.registry import NWRegistry, RegistryError, _normalize_version


# --- helpers ---

def make_registry(tmp_path, board_types=(), units=None):
    """Build a minimal NW-Registry directory structure under tmp_path."""
    (tmp_path / "units").mkdir()

    with open(tmp_path / "board_types.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["board_type", "device", "hw_version", "notes"])
        for row in board_types:
            w.writerow(row)

    for device, rows in (units or {}).items():
        path = tmp_path / "units" / f"{device.lower()}.csv"
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["board_type", "group_id", "individual_id",
                        "firmware_id", "hw_version", "location", "notes"])
            for row in rows:
                w.writerow(row)

    return NWRegistry(tmp_path)


# --- _normalize_version ---

def test_normalize_two_part():
    assert _normalize_version("3.0") == "3.0.0"

def test_normalize_three_part():
    assert _normalize_version("0.1.0") == "0.1.0"

def test_normalize_one_part():
    assert _normalize_version("2") == "2.0.0"


# --- NWRegistry init ---

def test_invalid_path_raises():
    with pytest.raises(RegistryError, match="not found"):
        NWRegistry("/nonexistent/path")


# --- next_individual_id ---

def test_next_id_no_units_file(tmp_path):
    reg = make_registry(tmp_path)  # no units created
    assert reg.next_individual_id("Margay", 0x4D03) == 1

def test_next_id_empty_units(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": []})
    assert reg.next_individual_id("Margay", 0x4D03) == 1

def test_next_id_existing_units(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "", ""],
        ["0x4D03", "0x4E57", "0x0002", "0x0000", "3.0.0", "", ""],
        ["0x4D03", "0x1701", "0x0003", "0x0000", "3.0.0", "", ""],
    ]})
    assert reg.next_individual_id("Margay", 0x4D03) == 4

def test_next_id_global_not_per_group(tmp_path):
    # IDs are global per board_type regardless of group
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0005", "0x0000", "3.0.0", "", ""],
        ["0x4D03", "0x1701", "0x0003", "0x0000", "3.0.0", "", ""],
    ]})
    assert reg.next_individual_id("Margay", 0x4D03) == 6

def test_next_id_ignores_other_board_types(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D02", "0x4E57", "0x0010", "0x0000", "2.2.0", "", ""],  # different board_type
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "", ""],
    ]})
    assert reg.next_individual_id("Margay", 0x4D03) == 2


# --- check_duplicate ---

def test_check_duplicate_found(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "", ""],
    ]})
    assert reg.check_duplicate("Margay", 0x4D03, 0x0001) is True

def test_check_duplicate_not_found(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "", ""],
    ]})
    assert reg.check_duplicate("Margay", 0x4D03, 0x0002) is False


# --- list_units ---

def test_list_units_empty(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": []})
    assert reg.list_units("Margay") == []

def test_list_units_no_file(tmp_path):
    reg = make_registry(tmp_path)
    assert reg.list_units("Margay") == []

def test_list_units_returns_all_rows(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "Iowa", ""],
        ["0x4D03", "0x4E57", "0x0002", "0x0000", "3.0.0", "Alaska", ""],
    ]})
    rows = reg.list_units("Margay")
    assert len(rows) == 2
    assert rows[0]["individual_id"] == "0x0001"

def test_list_units_filters_by_board_type(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D02", "0x4E57", "0x0001", "0x0000", "2.0.0", "", ""],
        ["0x4D03", "0x4E57", "0x0002", "0x0000", "3.0.0", "", ""],
    ]})
    rows = reg.list_units("Margay", board_type=0x4D03)
    assert len(rows) == 1
    assert rows[0]["individual_id"] == "0x0002"


# --- append_unit ---

def test_append_unit(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "", ""],
    ]})
    reg.append_unit("Margay", 0x4D03, 0x4E57, 0x0002, "3.0")

    rows = list(csv.DictReader(open(tmp_path / "units" / "margay.csv")))
    assert len(rows) == 2
    assert rows[1]["individual_id"] == "0x0002"
    assert rows[1]["firmware_id"] == "0x0000"
    assert rows[1]["hw_version"] == "3.0.0"

def test_append_unit_duplicate_raises(tmp_path):
    reg = make_registry(tmp_path, units={"Margay": [
        ["0x4D03", "0x4E57", "0x0001", "0x0000", "3.0.0", "", ""],
    ]})
    with pytest.raises(RegistryError, match="Duplicate"):
        reg.append_unit("Margay", 0x4D03, 0x4E57, 0x0001, "3.0")

def test_append_unit_missing_file_raises(tmp_path):
    reg = make_registry(tmp_path)  # no units files
    with pytest.raises(RegistryError, match="Units file not found"):
        reg.append_unit("Margay", 0x4D03, 0x4E57, 0x0001, "3.0")

def test_append_unit_location_notes(tmp_path):
    reg = make_registry(tmp_path, units={"Walrus": []})
    reg.append_unit("Walrus", 0x5702, 0x4E57, 0x0001, "0.2",
                    location="Iowa", notes="test unit")
    rows = list(csv.DictReader(open(tmp_path / "units" / "walrus.csv")))
    assert rows[0]["location"] == "Iowa"
    assert rows[0]["notes"] == "test unit"
