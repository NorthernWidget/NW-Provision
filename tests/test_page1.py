import struct

import pytest

from nw_provision.page1 import (
    LAYOUT_BLANK, LAYOUT_MARGAY, MARGAY_BAT_PERCENTAGE_WARNING, MARGAY_BAT_VOLTAGE_ERROR,
    MARGAY_BATTERY_DIVIDER, MARGAY_STEINHART_HART, PAGE1_BUILDERS, PAGE1_SIZE,
    build_blank_page1, build_margay_page1, decode_margay_page1, describe_page1,
    margay_model, page1_blank,
)


# --- margay_model: --hw-version to board model ---

def test_model_from_version_string():
    assert margay_model("3.0") == 3

def test_model_minor_version_ignored():
    # Margay.h: MODEL_2v0, MODEL_2v1, MODEL_2v2 all map to 2
    assert margay_model("2.1") == 2
    assert margay_model("2.2") == 2

def test_model_from_int():
    assert margay_model(1) == 1

def test_model_unknown_rejected():
    with pytest.raises(ValueError, match="unknown Margay model 4"):
        margay_model("4.0")

def test_model_garbage_rejected():
    with pytest.raises(ValueError):
        margay_model("three")


# --- build_margay_page1: divider table (Margay.cpp constructor) ---

def test_divider_table_matches_library():
    # Margay.cpp: models 2 and 3 → 2.0; model 1 → 2.0; the else branch (model 0) → 9.0
    assert MARGAY_BATTERY_DIVIDER == {0: 9.0, 1: 2.0, 2: 2.0, 3: 2.0}

def test_divider_model_3_little_endian():
    p = build_margay_page1("3.0")
    assert p[0x00:0x02] == bytes([0xD0, 0x07])   # 2000
    assert struct.unpack_from("<H", p, 0)[0] == 2000

def test_divider_model_0():
    p = build_margay_page1(0)
    assert struct.unpack_from("<H", p, 0)[0] == 9000

def test_divider_decodes_as_library_does():
    # Margay.cpp: BatteryDivider = Pages.get16(0x20) / 1000.0
    for model, divider in MARGAY_BATTERY_DIVIDER.items():
        p = build_margay_page1(model)
        assert struct.unpack_from("<H", p, 0)[0] / 1000.0 == divider


# --- build_margay_page1: constants round-trip (Margay.h) ---

def test_steinhart_hart_bytes_are_float32_of_constants():
    p = build_margay_page1(3)
    assert p[0x02:0x12] == struct.pack("<4f", *MARGAY_STEINHART_HART)

def test_steinhart_hart_decode_matches_float32_constants():
    # Pages.getFloat(0x22..0x2E) yields the float32 the library would hold after `float A = 0.003354016;`
    p = build_margay_page1(3)
    for stored, const in zip(decode_margay_page1(p)["steinhart_hart"], MARGAY_STEINHART_HART):
        assert struct.pack("<f", stored) == struct.pack("<f", const)

def test_battery_low_threshold():
    p = build_margay_page1(3)
    assert struct.unpack_from("<H", p, 0x12)[0] == 330          # 3.30 V in 0.01 V
    assert struct.unpack_from("<H", p, 0x12)[0] / 100.0 == MARGAY_BAT_VOLTAGE_ERROR

def test_battery_warning_percent():
    p = build_margay_page1(3)
    assert p[0x14] == MARGAY_BAT_PERCENTAGE_WARNING == 50

def test_reserved_bytes_zero():
    p = build_margay_page1(3)
    assert p[0x15:] == bytes(11)

def test_output_is_32_bytes():
    assert len(build_margay_page1(3)) == PAGE1_SIZE

def test_model_3_full_image():
    expected = bytes.fromhex(
        "D0070DCF5B3B0A2BA1394AFC2A37831B7435"   # divider 2000; A, B, C, D float32 LE
        "4A0132"                                 # 330 (3.30 V); 50 %
        "0000000000000000000000"                 # reserved
    )
    assert build_margay_page1("3.0") == expected

def test_overrides():
    p = build_margay_page1(3, steinhart_hart=(1.0, 2.0, 3.0, 4.0),
                           bat_voltage_error=3.5, bat_percentage_warning=40)
    assert struct.unpack_from("<4f", p, 0x02) == (1.0, 2.0, 3.0, 4.0)
    assert struct.unpack_from("<H", p, 0x12)[0] == 350
    assert p[0x14] == 40

def test_rejects_bad_warning():
    with pytest.raises(ValueError):
        build_margay_page1(3, bat_percentage_warning=101)


# --- blank page and the layout table ---

def test_blank_page1():
    assert build_blank_page1() == b"\xFF" * 32
    assert page1_blank(build_blank_page1())

def test_margay_page1_not_blank():
    assert not page1_blank(build_margay_page1(3))

def test_builders_table():
    assert PAGE1_BUILDERS[LAYOUT_MARGAY] is build_margay_page1
    assert PAGE1_BUILDERS[LAYOUT_BLANK] is build_blank_page1


# --- decode / describe ---

def test_decode_fields():
    f = decode_margay_page1(build_margay_page1("2.2"))
    assert f["battery_divider"] == 2.0
    assert f["bat_voltage_error"] == 3.3
    assert f["bat_percentage_warning"] == 50
    assert f["reserved"] == bytes(11)

def test_decode_wrong_length():
    with pytest.raises(ValueError):
        decode_margay_page1(bytes(31))

def test_describe_blank():
    assert describe_page1(b"\xFF" * 32).startswith("blank")

def test_describe_margay():
    text = describe_page1(build_margay_page1(0))
    assert "9.000" in text
    assert "0.003354016" in text
    assert "9.093712e-07" in text
    assert "3.30 V" in text
    assert "50 %" in text
    assert "all 0x00" in text

def test_describe_other_layout_not_decoded():
    text = describe_page1(bytes(range(32)), layout=LAYOUT_BLANK)
    assert "not decode" in text

def test_describe_wrong_length():
    with pytest.raises(ValueError):
        describe_page1(bytes(16))


# --- devices: which devices carry a Page 1 builder ---

def test_devices_page1_layouts():
    from nw_provision.devices import DEVICES
    assert DEVICES["Margay"].page1 == LAYOUT_MARGAY
    assert DEVICES["Okapi"].page1 == LAYOUT_BLANK
    for sensor in ("Apis", "Haar", "Walrus", "Libelle", "Liasis"):
        assert DEVICES[sensor].page1 is None, sensor

def test_device_layouts_have_builders():
    from nw_provision.devices import DEVICES
    for dev in DEVICES.values():
        if dev.page1 is not None:
            assert dev.page1 in PAGE1_BUILDERS, dev.name
