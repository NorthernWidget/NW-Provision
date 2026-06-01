import click
from .devices import DEVICES
from .page0 import build_page0, verify_page0


@click.group()
@click.version_option()
def main():
    """NW-Provision: write NW-Device-Specification Page 0 identity blocks to NorthernWidget boards."""


@main.command()
@click.option("--device",      required=True, type=click.Choice(sorted(DEVICES)), help="Device name")
@click.option("--hw-version",  required=True, help="Hardware version, e.g. 3.0")
@click.option("--fw-patch",    default=0, show_default=True, type=int, help="Firmware patch version")
@click.option("--group",       "group_id",  default=0, show_default=True, type=int, help="Group ID (0–65535)")
@click.option("--id",          "unique_id", required=True, type=int, help="Unique ID (0–65535)")
@click.option("--i2c-address", default=None, type=int,
              help="I2C address override (default: device default from table)")
@click.option("--dry-run",     is_flag=True, help="Print Page 0 bytes; do not write to hardware")
def write(device, hw_version, fw_patch, group_id, unique_id, i2c_address, dry_run):
    """Build and write a Page 0 identity block to a NorthernWidget board."""
    try:
        hw_major, hw_minor = (int(x) for x in hw_version.split("."))
    except ValueError:
        raise click.BadParameter("must be in major.minor format, e.g. 3.0", param_hint="--hw-version")

    dev = DEVICES[device]
    addr = i2c_address if i2c_address is not None else dev.i2c_address

    page0 = build_page0(
        device_name=device,
        hw_major=hw_major,
        hw_minor=hw_minor,
        fw_patch=fw_patch,
        group_id=group_id,
        unique_id=unique_id,
        i2c_address=addr,
    )

    click.echo(f"Device:      {device}")
    click.echo(f"HW version:  {hw_major}.{hw_minor}")
    click.echo(f"FW patch:    {fw_patch}")
    click.echo(f"Group ID:    {group_id} (0x{group_id:04X})")
    click.echo(f"Unique ID:   {unique_id} (0x{unique_id:04X})")
    click.echo(f"I2C address: 0x{addr:02X}" + (" [device default]" if addr == 0xFF else ""))
    click.echo(f"EEPROM:      {dev.eeprom_size} bytes — Page 0 at offset {dev.eeprom_size - 32} (0x{dev.eeprom_size - 32:04X})")
    click.echo("")
    _print_page0(page0)

    if dry_run:
        click.echo("\n[dry run — no hardware written]")
        return

    click.echo("\n[avrdude write not yet implemented]")


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
