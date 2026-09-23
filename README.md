# NW-Provision

Write [NW-Device-Specification](https://github.com/NorthernWidget/NW-Device-Specification) **Page 0** identity blocks, and a data logger's **Page 1** calibration, to NorthernWidget boards via avrdude.

NW-Provision replaces the manual `MargaySetup.ino` workflow (flash setup sketch → serial interaction → reflash). It reads the existing EEPROM, writes a freshly built identity block into Page 0 (the 32 bytes at `length-64`), writes the image back, and verifies the readback, without disturbing the firmware already on the board. Page 1 (the 32 bytes above Page 0) holds the device's calibration. For a data logger (Margay, Okapi) NW-Provision writes it from the board model. For a sensor it leaves Page 1 as found: the sensor's firmware owns it (Apis stores its zero there).

## Installation

```
pip install nw-provision
```

Requires Python ≥ 3.11 and `avrdude` on your PATH.

## Subcommands

### `write` — program a board

```
nw-provision write \
  --device Margay \
  --hw-version 3.0 \
  --id auto \
  --registry /path/to/NW-Registry \
  --programmer usbasp
```

`--id` accepts a decimal integer, a `0x`-prefixed hex value, or `auto`.  
`auto` queries the registry for the next available ID and asks for confirmation before writing.

For a Margay or an Okapi, `write` also builds Page 1 (calibration) and writes it beside Page 0. The major number of `--hw-version` is the board model: `3.0` gives model 3, `2.1` and `2.2` give model 2 (Margay_Library maps `MODEL_2v0`, `MODEL_2v1`, and `MODEL_2v2` to the same model), and `0.0` gives model 0. A Margay model outside 0–3 is refused unless you pass `--no-page1`. The bytes written decode to the constants built into Margay_Library (`Margay.h`). A freshly provisioned board therefore measures exactly as an unprovisioned one, and a per-board calibration can replace those constants later. Okapi_Library stores no calibration yet, and an Okapi gets a blank Page 1 (32 × `0xFF`). Pass `--no-page1` to leave Page 1 as found on either logger. A sensor's Page 1 is never written.

The readback verifies both pages: Page 0 by its CRC-8 and magic byte, Page 1 byte for byte against what was written.

Full options:

| Option | Default | Description |
|--------|---------|-------------|
| `--device` | required | Device name (see table below) |
| `--hw-version` | required | Hardware version in `major.minor` form, e.g. `3.0` |
| `--fw-patch` | `0` | Firmware patch version |
| `--group` | `0` | Group ID — decimal or `0x` hex, e.g. `0x4E57` |
| `--id` | required | Unique ID — decimal, `0x` hex, or `auto` |
| `--registry` | `$NW_REGISTRY_PATH` | Path to [NW-Registry](https://github.com/NorthernWidget/NW-Registry) directory |
| `--i2c-address` | device default | I2C address override |
| `--programmer` | — | avrdude programmer ID, e.g. `usbasp`, `avrisp2` |
| `--port` | — | Programmer port, e.g. `/dev/ttyUSB0` (omit if not needed) |
| `--part` | from device table | avrdude part override |
| `--location` | `""` | Deployment location note written to registry |
| `--notes` | `""` | Freeform notes written to registry |
| `--no-page1` | — | Leave Page 1 (calibration) as found on a data logger instead of writing it |
| `--dry-run` | — | Print the Page 0 (and Page 1) bytes; do not write to hardware |

Set `NW_REGISTRY_PATH` in your environment to avoid passing `--registry` every time:

```
export NW_REGISTRY_PATH=/path/to/NW-Registry
nw-provision write --device Margay --hw-version 3.0 --id auto --programmer usbasp
```

### `list` — query the registry

```
nw-provision list --device Haar
nw-provision list --device Margay --board-type 0x4D03
```

Displays a formatted table of all units for a device from the registry, with a summary line showing the count and next available ID. `--board-type` filters to a specific hardware version.

### `read` — display a board's identity block

```
nw-provision read --device Margay --programmer usbasp
```

Reads the full EEPROM, extracts Page 0 (the 32 bytes at `length-64`) and Page 1 (the 32 above it), prints both in a hex/ASCII table, and reports whether Page 0 passes Schema 1 validation. Under the Page 1 bytes it prints their decoding. For a Margay that is the battery divider, the four Steinhart–Hart coefficients, and the battery thresholds (the layout below). Any device's page reads `blank` when every byte is `0xFF`. A sensor's layout belongs to its firmware, and `read` reports only whether the page holds data.

### `verify` — validate raw hex bytes

```
nw-provision verify 01 4D 61 72 67 61 79 00 03 00 02 ...
```

Accepts 32 space-separated hex bytes and validates them offline (no hardware needed).

## Supported devices

| Device  | MCU          | EEPROM | avrdude part | I2C address | board_type high byte |
|---------|-------------|--------|-------------|-------------|----------------------|
| Margay  | ATmega1284P | 4096 B | m1284p      | —           | 0x4D |
| Okapi   | ATmega1284P | 4096 B | m1284p      | —           | 0x4F |
| Apis    | ATtiny1634  | 256 B  | t1634       | 0x41        | 0x6C |
| Haar    | ATtiny1634  | 256 B  | t1634       | 0x48        | 0x48 |
| Walrus  | ATtiny1634  | 256 B  | t1634       | 0x57        | 0x57 |
| Libelle | ATtiny841   | 512 B  | t841        | 0x4C        | 0x23 |
| Liasis  | — (future)  | —      | —           | —           | 0x24 |

`board_type` written to the EEPROM is computed as `(board_type_high << 8) | hw_major` per Schema 1.

## Page 0 layout (Schema 1)

```
Offset  Bytes  Contents
0x00    1      Schema byte (0x01)
0x01    7      Device name, ASCII, null-padded
0x08    1      HW major
0x09    1      HW minor
0x0A    1      FW patch
0x0B    5      Reserved (0x00)
0x10    2      board_type (big-endian)
0x12    2      group_id (big-endian)
0x14    2      unique_id (big-endian)
0x16    2      Reserved (0x00)
0x18    6      Reserved (0x00)
0x1E    1      CRC-8 over 0x00–0x1D
0x1F    1      I2C address (0xFF = device default)
```

Physical location: `EEPROM[length-64]` through `EEPROM[length-33]`; Page 1 (calibration) occupies `EEPROM[length-32]` through `EEPROM[length-1]`. The two are one 64-byte stored image in bus order (NW-Device-Specification, renumbered 2026-09-23).

## Page 1 layout (Margay calibration)

Bus addresses `0x20`–`0x3F`. The layout is the Margay appendix of NW-Device-Specification. Margay_Library reads the page at boot and falls back to its built-in constants when the page is blank.

```
Offset       Bytes  Contents
0x20–0x21    2      Battery divider × 1000, uint16 little-endian
0x22–0x25    4      Thermistor Steinhart–Hart A, float32 little-endian
0x26–0x29    4      Thermistor Steinhart–Hart B, float32 little-endian
0x2A–0x2D    4      Thermistor Steinhart–Hart C, float32 little-endian
0x2E–0x31    4      Thermistor Steinhart–Hart D, float32 little-endian
0x32–0x33    2      Battery low threshold, uint16, 0.01 V (330 = 3.30 V)
0x34         1      Battery warning, uint8, percent
0x35–0x3F    11     Reserved (0x00)
```

The values NW-Provision writes are those in `Margay_Library/src/Margay.h` and the constructor in `Margay.cpp`:

| Field | Model 0 | Models 1, 2, 3 | Source |
|-------|---------|----------------|--------|
| Battery divider | 9.0 (`9000`) | 2.0 (`2000`) | `Margay.cpp` constructor, `BatteryDivider` per model |
| Steinhart–Hart A | 0.003354016 | 0.003354016 | `Margay.h` |
| Steinhart–Hart B | 0.0003074038 | 0.0003074038 | `Margay.h` |
| Steinhart–Hart C | 1.019153E-05 | 1.019153E-05 | `Margay.h` |
| Steinhart–Hart D | 9.093712E-07 | 9.093712E-07 | `Margay.h` |
| Battery low threshold | 3.30 V (`330`) | 3.30 V (`330`) | `Margay.h`, `BatVoltageError` |
| Battery warning | 50 % | 50 % | `Margay.h`, `BatPercentageWarning` |

Model 3.0 in full, as `nw-provision write --device Margay --hw-version 3.0 --id 1 --dry-run` prints it:

```
0x20  D0 07 0D CF 5B 3B 0A 2B
0x28  A1 39 4A FC 2A 37 83 1B
0x30  74 35 4A 01 32 00 00 00
0x38  00 00 00 00 00 00 00 00
```

An Okapi's Page 1 is written blank (32 × `0xFF`) until Okapi_Library reads a calibration from it.

## NW-Registry integration

[NW-Registry](https://github.com/NorthernWidget/NW-Registry) is the companion CSV database of programmed boards. When `--registry` is provided:

- `--id auto` queries `units/<device>.csv` for the highest `individual_id` with the matching `board_type`, increments it, and prompts for confirmation.
- After a successful write, the new unit row is appended to the registry automatically, including any `--location` and `--notes` provided.
- If a manually-specified `--id` already exists, a warning is shown and confirmation is required to continue.

`individual_id` increments globally per `board_type`, not per group.

## Development

```
git clone https://github.com/NorthernWidget/NW-Provision
cd NW-Provision
pip install -e ".[dev]"
pytest
```

## License

GPL-3.0-or-later — see [LICENSE.md](LICENSE.md).
