import pytest
from nw_provision.page0 import build_page0, crc8, verify_page0, PAGE0_SIZE, SCHEMA_1


def margay(**kwargs):
    defaults = dict(device_name="Margay", hw_major=3, hw_minor=0, fw_patch=2,
                    group_id=0, unique_id=1, board_type_high=0x4D)
    defaults.update(kwargs)
    return build_page0(**defaults)


# --- crc8 ---

def test_crc8_zero():
    assert crc8(b"\x00") == 0x00

def test_crc8_one():
    assert crc8(b"\x01") == 0x07

def test_crc8_self_consistent():
    data = bytes(range(30))
    c = crc8(data)
    assert 0 <= c <= 255


# --- build_page0 structure ---

def test_schema_byte():
    assert margay()[0x00] == SCHEMA_1

def test_name_margay():
    p = margay()
    assert p[0x01:0x07] == b"Margay"
    assert p[0x07] == 0x00  # null pad (6 chars → pad 1)

def test_name_libelle_fills_field():
    p = build_page0("Libelle", hw_major=1, hw_minor=0, fw_patch=0,
                    group_id=0, unique_id=0, board_type_high=0x23)
    assert p[0x01:0x08] == b"Libelle"  # exactly 7 chars, no pad needed

def test_name_truncates_at_7():
    p = build_page0("ABCDEFGH", hw_major=1, hw_minor=0, fw_patch=0,
                    group_id=0, unique_id=0, board_type_high=0x41)
    assert p[0x01:0x08] == b"ABCDEFG"

def test_hw_version():
    p = build_page0("Margay", hw_major=3, hw_minor=2, fw_patch=0,
                    group_id=0, unique_id=0, board_type_high=0x4D)
    assert p[0x08] == 3
    assert p[0x09] == 2

def test_fw_patch():
    p = margay(fw_patch=7)
    assert p[0x0A] == 7

def test_board_type_high_byte_from_argument():
    p = margay(board_type_high=0x4D)
    assert p[0x10] == 0x4D

def test_board_type_high_legacy_code():
    # Apis uses legacy 0x6C ("Project Symbiont Lidar"), not ASCII('A')=0x41
    p = build_page0("Apis", hw_major=1, hw_minor=0, fw_patch=0,
                    group_id=0, unique_id=0, board_type_high=0x6C)
    assert p[0x10] == 0x6C

def test_board_type_low_byte_is_hw_major():
    p = margay(hw_major=3)
    assert p[0x11] == 3

def test_group_id_big_endian():
    p = build_page0("Margay", hw_major=3, hw_minor=0, fw_patch=0,
                    group_id=0x0102, unique_id=0, board_type_high=0x4D)
    assert p[0x12] == 0x01
    assert p[0x13] == 0x02

def test_unique_id_big_endian():
    p = build_page0("Margay", hw_major=3, hw_minor=0, fw_patch=0,
                    group_id=0, unique_id=0x002A, board_type_high=0x4D)
    assert p[0x14] == 0x00
    assert p[0x15] == 0x2A

def test_reserved_bytes_zero():
    p = margay()
    reserved = list(range(0x0B, 0x10)) + [0x16, 0x17] + list(range(0x18, 0x1E))
    for i in reserved:
        assert p[i] == 0x00, f"byte 0x{i:02X} should be 0x00"

def test_crc_stored_correctly():
    p = margay()
    assert p[0x1E] == crc8(p[0x00:0x1E])

def test_i2c_address_default():
    p = margay()
    assert p[0x1F] == 0xFF

def test_i2c_address_override():
    p = build_page0("Walrus", hw_major=2, hw_minor=0, fw_patch=0,
                    group_id=0, unique_id=0, board_type_high=0x57, i2c_address=0x57)
    assert p[0x1F] == 0x57

def test_output_is_32_bytes():
    assert len(margay()) == PAGE0_SIZE


# --- range validation ---

def test_rejects_hw_major_out_of_range():
    with pytest.raises(ValueError):
        build_page0("Margay", hw_major=256, hw_minor=0, fw_patch=0,
                    group_id=0, unique_id=0, board_type_high=0x4D)

def test_rejects_group_id_out_of_range():
    with pytest.raises(ValueError):
        build_page0("Margay", hw_major=1, hw_minor=0, fw_patch=0,
                    group_id=0x10000, unique_id=0, board_type_high=0x4D)

def test_rejects_unique_id_out_of_range():
    with pytest.raises(ValueError):
        build_page0("Margay", hw_major=1, hw_minor=0, fw_patch=0,
                    group_id=0, unique_id=0x10000, board_type_high=0x4D)


# --- verify_page0 ---

def test_verify_valid():
    ok, errors = verify_page0(margay())
    assert ok
    assert errors == []

def test_verify_bad_crc():
    p = bytearray(margay())
    p[0x1E] ^= 0xFF  # corrupt CRC
    ok, errors = verify_page0(bytes(p))
    assert not ok
    assert any("CRC" in e for e in errors)

def test_verify_unprogrammed():
    ok, errors = verify_page0(b"\xFF" * 32)
    assert not ok
    assert any("0xFF" in e for e in errors)

def test_verify_schema0():
    p = bytearray(32)
    ok, errors = verify_page0(bytes(p))
    assert not ok
    assert any("Schema 0" in e for e in errors)

def test_verify_wrong_length():
    ok, errors = verify_page0(b"\x01" * 16)
    assert not ok
