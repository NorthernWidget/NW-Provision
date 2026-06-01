"""
Interface to an NW-Registry directory (board_types.csv + units/*.csv).

Registry layout:
  board_types.csv          — board_type (hex) → device, hw_version, notes
  units/<device>.csv       — one row per programmed board

All ID fields in the CSV use 0x-prefixed, zero-padded 4-digit hex (e.g. 0x4D03).
"""

import csv
from pathlib import Path


class RegistryError(Exception):
    pass


def _normalize_version(v: str) -> str:
    """Pad a version string to 3 parts: '3.0' → '3.0.0'."""
    parts = v.strip().split(".")
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:3])


def _parse_hex(s: str) -> int:
    return int(s.strip(), 16)


def _fmt_hex(v: int) -> str:
    return f"0x{v:04X}"


class NWRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_dir():
            raise RegistryError(f"Registry path not found: {self.path}")

    def _units_path(self, device: str) -> Path:
        return self.path / "units" / f"{device.lower()}.csv"

    def next_individual_id(self, device: str, board_type: int) -> int:
        """Return max individual_id across all groups for board_type, plus 1.

        Returns 1 if no units exist yet for this board_type.
        individual_id is globally incrementing per board_type (not per group).
        """
        path = self._units_path(device)
        if not path.exists():
            return 1
        max_id = 0
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if _parse_hex(row["board_type"]) == board_type:
                    uid = _parse_hex(row["individual_id"])
                    if uid > max_id:
                        max_id = uid
        return max_id + 1

    def check_duplicate(self, device: str, board_type: int, individual_id: int) -> bool:
        """Return True if (board_type, individual_id) already exists in units CSV."""
        path = self._units_path(device)
        if not path.exists():
            return False
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if (_parse_hex(row["board_type"]) == board_type and
                        _parse_hex(row["individual_id"]) == individual_id):
                    return True
        return False

    def append_unit(
        self,
        device: str,
        board_type: int,
        group_id: int,
        individual_id: int,
        hw_version: str,
        location: str = "",
        notes: str = "",
    ) -> None:
        """Append a new unit row to units/<device>.csv.

        Raises RegistryError on duplicate or missing units file.
        """
        path = self._units_path(device)
        if not path.exists():
            raise RegistryError(f"Units file not found: {path}")
        if self.check_duplicate(device, board_type, individual_id):
            raise RegistryError(
                f"Duplicate: {device} board_type={_fmt_hex(board_type)} "
                f"individual_id={_fmt_hex(individual_id)} already in registry"
            )
        row = {
            "board_type":    _fmt_hex(board_type),
            "group_id":      _fmt_hex(group_id),
            "individual_id": _fmt_hex(individual_id),
            "firmware_id":   "0x0000",
            "hw_version":    _normalize_version(hw_version),
            "location":      location,
            "notes":         notes,
        }
        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writerow(row)
