"""
Build and decode the 32-byte NW-Device-Specification Page 1 calibration block of a data logger.

Physical location: EEPROM[length-32] through EEPROM[length-1], directly above Page 0.
Bus addresses 0x20–0x3F; the offsets below are bus addresses.

Margay layout (NW-Device-Specification, Margay appendix, "Page 1 (0x20–0x3F): Calibration"):
  0x20–0x21   Battery divider × 1000, uint16 little-endian
  0x22–0x31   Thermistor Steinhart–Hart A, B, C, D, float32 each, little-endian
  0x32–0x33   Battery low threshold, uint16, 0.01 V (330 = 3.30 V)
  0x34        Battery warning, uint8, percent
  0x35–0x3F   Reserved (0x00)

Margay_Library reads this page at boot (Margay.cpp, "Calibration from Page 1") and falls
back to its built-in constants when every byte is 0xFF. The values here are those constants,
so a freshly provisioned board behaves exactly as an unprovisioned one.

Sensors have no builder here: their Page 1 is written by their own firmware (Apis stores its
zero there) and provisioning leaves it as found.
"""

import struct

PAGE1_SIZE = 32
PAGE1_BASE = 0x20   # bus address of the first Page 1 byte

# Margay_Library/src/Margay.cpp, constructor: BatteryDivider per board model.
# Model 0 (v0.0 prototype) took the 9.0 branch in 2018 (commit 1d897ce) and still does;
# models 1, 2 (v2.0–v2.2 share a pin map) and 3 all set 2.0.
MARGAY_BATTERY_DIVIDER = {
    0: 9.0,
    1: 2.0,
    2: 2.0,
    3: 2.0,
}

# Margay_Library/src/Margay.h: thermistor Steinhart–Hart coefficients and battery thresholds.
MARGAY_STEINHART_HART = (0.003354016, 0.0003074038, 1.019153E-05, 9.093712E-07)  # A, B, C, D
MARGAY_BAT_VOLTAGE_ERROR = 3.3       # V; BatVoltageError
MARGAY_BAT_PERCENTAGE_WARNING = 50   # %; BatPercentageWarning

# Named layouts a device can carry in its table entry (devices.py).
LAYOUT_MARGAY = "margay"   # the calibration block above, built from the board model
LAYOUT_BLANK = "blank"     # 32 × 0xFF: the device stores no calibration yet


def margay_model(model: str | int) -> int:
    """The Margay board model (0–3) from a hardware version string or an integer.

    "3.0" → 3, "2.1" → 2, 3 → 3. The minor version does not change the model:
    Margay.h maps MODEL_2v0, MODEL_2v1, and MODEL_2v2 all to 2.
    """
    if isinstance(model, str):
        try:
            model = int(model.split(".")[0])
        except ValueError:
            raise ValueError(f"model must be major.minor or an integer, got {model!r}")
    if model not in MARGAY_BATTERY_DIVIDER:
        known = ", ".join(str(m) for m in MARGAY_BATTERY_DIVIDER)
        raise ValueError(f"unknown Margay model {model}; known models: {known}")
    return model


def build_margay_page1(
    model: str | int,
    steinhart_hart: tuple[float, float, float, float] = MARGAY_STEINHART_HART,
    bat_voltage_error: float = MARGAY_BAT_VOLTAGE_ERROR,
    bat_percentage_warning: int = MARGAY_BAT_PERCENTAGE_WARNING,
) -> bytes:
    """Return the 32-byte Page 1 calibration block for a Margay of the given model."""
    divider = MARGAY_BATTERY_DIVIDER[margay_model(model)]
    divider_x1000 = round(divider * 1000)
    bat_low_x100 = round(bat_voltage_error * 100)
    if not 0 <= bat_low_x100 <= 0xFFFF:
        raise ValueError(f"bat_voltage_error {bat_voltage_error} V out of range 0–655.35")
    if not 0 <= bat_percentage_warning <= 100:
        raise ValueError(f"bat_percentage_warning {bat_percentage_warning} out of range 0–100")
    if len(steinhart_hart) != 4:
        raise ValueError(f"steinhart_hart needs 4 coefficients, got {len(steinhart_hart)}")

    buf = bytearray(PAGE1_SIZE)  # initialised to 0x00: the reserved bytes stay so

    struct.pack_into("<H", buf, 0x20 - PAGE1_BASE, divider_x1000)
    struct.pack_into("<4f", buf, 0x22 - PAGE1_BASE, *steinhart_hart)
    struct.pack_into("<H", buf, 0x32 - PAGE1_BASE, bat_low_x100)
    buf[0x34 - PAGE1_BASE] = bat_percentage_warning
    # 0x35–0x3F: reserved = 0x00

    return bytes(buf)


def build_blank_page1(model: str | int = 0) -> bytes:
    """Return a Page 1 of 32 × 0xFF: the unprogrammed state every library treats as 'no calibration'."""
    return b"\xFF" * PAGE1_SIZE


PAGE1_BUILDERS = {
    LAYOUT_MARGAY: build_margay_page1,
    LAYOUT_BLANK: build_blank_page1,
}


def page1_blank(data: bytes) -> bool:
    """True when every byte is 0xFF (NW_Pages::page1Blank in NW_Core)."""
    return all(b == 0xFF for b in data)


def decode_margay_page1(data: bytes) -> dict:
    """Decode a Margay Page 1 into its fields.

    Floats come back as the float32 values stored, not the double constants they were
    built from; compare with struct.pack('<f', ...) rather than ==.
    """
    if len(data) != PAGE1_SIZE:
        raise ValueError(f"expected {PAGE1_SIZE} bytes, got {len(data)}")
    (divider_x1000,) = struct.unpack_from("<H", data, 0x20 - PAGE1_BASE)
    a, b, c, d = struct.unpack_from("<4f", data, 0x22 - PAGE1_BASE)
    (bat_low_x100,) = struct.unpack_from("<H", data, 0x32 - PAGE1_BASE)
    return {
        "battery_divider": divider_x1000 / 1000.0,
        "steinhart_hart": (a, b, c, d),
        "bat_voltage_error": bat_low_x100 / 100.0,
        "bat_percentage_warning": data[0x34 - PAGE1_BASE],
        "reserved": bytes(data[0x35 - PAGE1_BASE:]),
    }


def describe_page1(data: bytes, layout: str | None = LAYOUT_MARGAY) -> str:
    """Human-readable decoding of a Page 1 block, one field per line.

    An all-0xFF page is "blank" whatever the layout. A non-blank page is decoded
    only for LAYOUT_MARGAY; other layouts report that the page holds data.
    """
    if len(data) != PAGE1_SIZE:
        raise ValueError(f"expected {PAGE1_SIZE} bytes, got {len(data)}")
    if page1_blank(data):
        return "blank (all 0xFF): the library uses its built-in constants"
    if layout != LAYOUT_MARGAY:
        return "not blank: holds data this tool does not decode"
    f = decode_margay_page1(data)
    a, b, c, d = f["steinhart_hart"]
    reserved = ("all 0x00" if not any(f["reserved"])
                else " ".join(f"{x:02X}" for x in f["reserved"]))
    return "\n".join([
        f"Battery divider:     {f['battery_divider']:.3f}  (0x20: {round(f['battery_divider'] * 1000)})",
        f"Steinhart-Hart A:    {a:.7g}",
        f"Steinhart-Hart B:    {b:.7g}",
        f"Steinhart-Hart C:    {c:.7g}",
        f"Steinhart-Hart D:    {d:.7g}",
        f"Battery low:         {f['bat_voltage_error']:.2f} V  (0x32: {round(f['bat_voltage_error'] * 100)})",
        f"Battery warning:     {f['bat_percentage_warning']} %",
        f"Reserved 0x35-0x3F:  {reserved}",
    ])
