import click
from .avrdude import AvrdudeError, patch_eeprom, read_eeprom, write_eeprom
from .devices import DEVICES
from .page0 import build_page0, verify_page0
from .registry import NWRegistry, RegistryError

_PROGRAMMABLE = sorted(k for k, v in DEVICES.items() if v.has_mcu)


def _parse_int(s: str, param_hint: str) -> int:
    """Parse a decimal or 0x-hex integer string; raise BadParameter on failure."""
    try:
        return int(s, 0)
    except ValueError:
        raise click.BadParameter(f"expected an integer (decimal or 0x hex), got {s!r}",
                                 param_hint=param_hint)


def _resolve_registry(registry_path: str | None) -> NWRegistry | None:
    if registry_path:
        try:
            return NWRegistry(registry_path)
        except RegistryError as e:
            raise click.ClickException(str(e))
    return None


@click.group()
@click.version_option()
def main():
    """NW-Provision: write NW-Device-Specification Page 0 identity blocks to NorthernWidget boards."""


@main.command()
@click.option("--device",      required=True, type=click.Choice(_PROGRAMMABLE), help="Device name")
@click.option("--hw-version",  required=True, help="Hardware version, e.g. 3.0")
@click.option("--fw-patch",    default=0, show_default=True, type=int, help="Firmware patch version")
@click.option("--group",       "group_id_str", default="0", show_default=True,
              help="Group ID — decimal or 0x hex, e.g. 0x4E57")
@click.option("--id",          "unique_id_str", required=True,
              help="Unique ID — decimal, 0x hex, or 'auto' (requires --registry)")
@click.option("--registry",    "registry_path", default=None, envvar="NW_REGISTRY_PATH",
              help="Path to NW-Registry directory (or set NW_REGISTRY_PATH)")
@click.option("--i2c-address", default=None, type=int,
              help="I2C address override (default: device default from table)")
@click.option("--programmer",  default=None, help="avrdude programmer ID, e.g. usbasp, avrisp2")
@click.option("--port",        default=None, help="Programmer port, e.g. /dev/ttyUSB0 (omit if not needed)")
@click.option("--part",        default=None, help="avrdude part override (default: from device table)")
@click.option("--location",    default="", help="Physical location note written to registry")
@click.option("--notes",       default="", help="Freeform notes written to registry")
@click.option("--dry-run",     is_flag=True, help="Print Page 0 bytes; do not write to hardware")
def write(device, hw_version, fw_patch, group_id_str, unique_id_str, registry_path,
          i2c_address, programmer, port, part, location, notes, dry_run):
    """Build and write a Page 0 identity block to a NorthernWidget board."""
    try:
        hw_major, hw_minor = (int(x) for x in hw_version.split("."))
    except ValueError:
        raise click.BadParameter("must be in major.minor format, e.g. 3.0", param_hint="--hw-version")

    group_id = _parse_int(group_id_str, "--group")
    dev = DEVICES[device]
    reg = _resolve_registry(registry_path)

    # board_type: high byte from device table, low byte = hw_major (Schema 1 convention)
    board_type = (dev.board_type_high << 8) | hw_major

    # Resolve unique_id
    if unique_id_str.lower() == "auto":
        if reg is None:
            raise click.UsageError("--id auto requires --registry or NW_REGISTRY_PATH")
        try:
            proposed = reg.next_individual_id(device, board_type)
        except RegistryError as e:
            raise click.ClickException(str(e))
        click.echo(f"Next available ID: {proposed} (0x{proposed:04X})")
        click.confirm("Use this ID?", abort=True)
        unique_id = proposed
    else:
        unique_id = _parse_int(unique_id_str, "--id")
        if reg and reg.check_duplicate(device, board_type, unique_id):
            click.echo(f"Warning: ID 0x{unique_id:04X} already exists in registry for "
                       f"{device} board_type 0x{board_type:04X}.", err=True)
            click.confirm("Continue anyway?", abort=True)

    addr = i2c_address if i2c_address is not None else dev.i2c_address

    page0 = build_page0(
        device_name=device,
        hw_major=hw_major,
        hw_minor=hw_minor,
        fw_patch=fw_patch,
        group_id=group_id,
        unique_id=unique_id,
        board_type=board_type,
        i2c_address=addr,
    )

    click.echo(f"Device:      {device}")
    click.echo(f"HW version:  {hw_major}.{hw_minor}  (board_type 0x{board_type:04X})")
    click.echo(f"FW patch:    {fw_patch}")
    click.echo(f"Group ID:    0x{group_id:04X}")
    click.echo(f"Unique ID:   0x{unique_id:04X}")
    click.echo(f"I2C address: 0x{addr:02X}" + (" [device default]" if addr == 0xFF else ""))
    click.echo(f"EEPROM:      {dev.eeprom_size} bytes — Page 0 at offset {dev.eeprom_size - 32} (0x{dev.eeprom_size - 32:04X})")
    click.echo("")
    _print_page0(page0)

    if dry_run:
        click.echo("\n[dry run — no hardware written]")
        return

    if not programmer:
        raise click.UsageError("--programmer is required (e.g. --programmer usbasp)")

    avrdude_part = part or dev.avrdude_part

    try:
        click.echo(f"\nReading EEPROM via {programmer} ({avrdude_part})...")
        eeprom = read_eeprom(programmer, avrdude_part, port)

        if len(eeprom) != dev.eeprom_size:
            raise click.ClickException(
                f"Read {len(eeprom)} bytes but {device} expects {dev.eeprom_size}"
            )

        patched = patch_eeprom(eeprom, page0)

        click.echo("Writing patched EEPROM...")
        write_eeprom(programmer, avrdude_part, patched, port)

        click.echo("Verifying readback...")
        readback = read_eeprom(programmer, avrdude_part, port)
        ok, errors = verify_page0(readback[-32:])
        if not ok:
            for msg in errors:
                click.echo(f"VERIFY FAIL: {msg}", err=True)
            raise SystemExit(1)

        click.echo("OK — Page 0 verified on device.")

    except AvrdudeError as e:
        raise click.ClickException(str(e))

    # Update registry after confirmed successful write
    if reg:
        try:
            reg.append_unit(device, board_type, group_id, unique_id, hw_version,
                            location=location, notes=notes)
            click.echo(f"Registry updated: {device} 0x{board_type:04X} "
                       f"group=0x{group_id:04X} id=0x{unique_id:04X}")
        except RegistryError as e:
            click.echo(f"Warning: registry not updated — {e}", err=True)


@main.command()
@click.option("--device",     required=True, type=click.Choice(_PROGRAMMABLE), help="Device name")
@click.option("--programmer", required=True, help="avrdude programmer ID, e.g. usbasp, avrisp2")
@click.option("--port",       default=None,  help="Programmer port (omit if not needed)")
@click.option("--part",       default=None,  help="avrdude part override (default: from device table)")
def read(device, programmer, port, part):
    """Read and display the Page 0 identity block from a connected board."""
    dev = DEVICES[device]
    avrdude_part = part or dev.avrdude_part

    try:
        click.echo(f"Reading EEPROM via {programmer} ({avrdude_part})...")
        eeprom = read_eeprom(programmer, avrdude_part, port)
    except AvrdudeError as e:
        raise click.ClickException(str(e))

    if len(eeprom) != dev.eeprom_size:
        raise click.ClickException(
            f"Read {len(eeprom)} bytes but {device} expects {dev.eeprom_size}"
        )

    page0 = eeprom[-32:]
    click.echo("")
    _print_page0(page0)
    click.echo("")

    ok, errors = verify_page0(page0)
    if ok:
        click.echo("OK — Page 0 is valid Schema 1")
    else:
        for msg in errors:
            click.echo(f"FAIL: {msg}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("hexbytes", nargs=-1)
def verify(hexbytes):
    """Verify a 32-byte Page 0 block passed as hex bytes.

    Example: nw-provision verify 01 4D 61 72 67 61 79 00 03 00 02 ...
    """
    if not hexbytes:
        raise click.UsageError("provide 32 hex bytes, e.g.: nw-provision verify 01 4D 61 ...")
    try:
        data = bytes(int(h, 16) for h in hexbytes)
    except ValueError as e:
        raise click.BadParameter(str(e))
    ok, errors = verify_page0(data)
    _print_page0(data)
    click.echo("")
    if ok:
        click.echo("OK — Page 0 is valid Schema 1")
    else:
        for msg in errors:
            click.echo(f"FAIL: {msg}", err=True)
        raise SystemExit(1)


_BLOCK_LABELS = [
    "Block 0  schema + name",
    "Block 1  version",
    "Block 2  serial number",
    "Block 3  integrity + admin",
]


def _print_page0(data: bytes) -> None:
    for block in range(4):
        offset = block * 8
        row = data[offset : offset + 8]
        hex_str = " ".join(f"{b:02X}" for b in row)
        ascii_str = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in row)
        click.echo(f"  0x{offset:02X}  {hex_str}  |{ascii_str}|  {_BLOCK_LABELS[block]}")
