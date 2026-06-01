# NW-Provision

Write [NW-Device-Specification](https://github.com/NorthernWidget/NW-Device-Specification) **Page 0** identity blocks to NorthernWidget boards via avrdude.

NW-Provision replaces the manual `MargaySetup.ino` workflow (flash setup sketch → serial interaction → reflash). It reads the existing EEPROM, patches the top 32 bytes with a freshly-built identity block, writes it back, and verifies the readback — without disturbing the firmware already on the board.

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
| `--dry-run` | — | Print Page 0 bytes; do not write to hardware |

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

Reads the full EEPROM, extracts the top 32 bytes, prints them in a hex/ASCII table, and reports whether Page 0 passes Schema 1 validation.

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

Physical location: `EEPROM[length-32]` through `EEPROM[length-1]`.

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
