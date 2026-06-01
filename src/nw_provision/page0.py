"""
Build and validate the 32-byte NW-Device-Specification Page 0 identity block.

Physical location: EEPROM[length-32] through EEPROM[length-1].
I2C register map:  byte offset within Page 0 == I2C address (0x00–0x1F).

Layout (Schema 1):
  0x00        Schema byte (0x01)
  0x01–0x07   Device name, 7-byte ASCII, null-padded
  0x08        HW major
  0x09        HW minor
  0x0A        FW patch  (NW combined-repo convention; 0x0B–0x0D = 0x00)
  0x0B–0x0F   Reserved (0x00)
  0x10–0x11   Board type (2 bytes, from NW-Registry board_types.csv)
  0x12–0x13   Group ID (big-endian uint16)
  0x14–0x15   Unique ID (big-endian uint16)
  0x16–0x17   FirmwareID legacy (0x00)
  0x18–0x1C   Reserved (0x00)
  0x1D        Magic byte (0x00, purpose TBD)
  0x1E        CRC-8 over bytes 0x00–0x1D
  0x1F        I2C address (0xFF = use device default)
"""

PAGE0_SIZE = 32
SCHEMA_1 = 0x01


def crc8(data: bytes) -> int:
    """CRC-8, polynomial 0x07, init 0x00."""
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc


def build_page0(
    device_name: str,
    hw_major: int,
    hw_minor: int,
    fw_patch: int,
    group_id: int,
    unique_id: int,
    board_type: int,
    i2c_address: int = 0xFF,
) -> bytes:
    """Return the 32-byte Page 0 block for a NW device."""
    if not 0 <= hw_major <= 255:
        raise ValueError(f"hw_major {hw_major} out of range 0–255")
    if not 0 <= hw_minor <= 255:
        raise ValueError(f"hw_minor {hw_minor} out of range 0–255")
    if not 0 <= fw_patch <= 255:
        raise ValueError(f"fw_patch {fw_patch} out of range 0–255")
    if not 0 <= group_id <= 0xFFFF:
        raise ValueError(f"group_id {group_id} out of range 0–65535")
    if not 0 <= unique_id <= 0xFFFF:
        raise ValueError(f"unique_id {unique_id} out of range 0–65535")

    buf = bytearray(PAGE0_SIZE)  # initialised to 0x00

    # Block 0: schema + name
    buf[0x00] = SCHEMA_1
    name_bytes = device_name.encode("ascii")[:7]
    buf[0x01 : 0x01 + len(name_bytes)] = name_bytes

    # Block 1: version
    buf[0x08] = hw_major
    buf[0x09] = hw_minor
    buf[0x0A] = fw_patch
    # 0x0B–0x0F: stay 0x00

    # Block 2: serial number
    buf[0x10] = (board_type >> 8) & 0xFF
    buf[0x11] = board_type & 0xFF
    buf[0x12] = (group_id >> 8) & 0xFF
    buf[0x13] = group_id & 0xFF
    buf[0x14] = (unique_id >> 8) & 0xFF
    buf[0x15] = unique_id & 0xFF
    # 0x16–0x17: FirmwareID legacy = 0x00

    # Block 3: integrity + admin
    # 0x18–0x1C: reserved = 0x00
    # 0x1D: magic byte = 0x00 (TBD)
    buf[0x1E] = crc8(bytes(buf[0x00:0x1E]))
    buf[0x1F] = i2c_address & 0xFF

    return bytes(buf)


def verify_page0(data: bytes) -> tuple[bool, list[str]]:
    """Check a 32-byte block for basic Page 0 validity.

    Returns (ok, [list of failure reasons]).
    """
    errors = []
    if len(data) != PAGE0_SIZE:
        return False, [f"expected {PAGE0_SIZE} bytes, got {len(data)}"]
    if data[0x00] == 0xFF:
        errors.append("schema byte is 0xFF (unprogrammed EEPROM)")
    elif data[0x00] == 0x00:
        errors.append("schema byte is 0x00 (Schema 0 legacy — not auto-detectable)")
    elif data[0x00] != SCHEMA_1:
        errors.append(f"unknown schema byte 0x{data[0x00]:02X}")
    expected_crc = crc8(data[0x00:0x1E])
    if data[0x1E] != expected_crc:
        errors.append(f"CRC mismatch: stored 0x{data[0x1E]:02X}, computed 0x{expected_crc:02X}")
    return len(errors) == 0, errors
