from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    name: str           # up to 7 ASCII chars; written to Page 0 bytes 0x01–0x07
    eeprom_size: int    # total EEPROM bytes; Page 0 lives at eeprom_size - 32
    avrdude_part: str   # avrdude -p argument
    i2c_address: int    # default I2C address written to Page 0 byte 0x1F;
                        # 0xFF = not a peripheral / use device default


DEVICES = {
    "Margay":  Device("Margay",  4096, "m1284p", 0xFF),   # logger; not an I2C peripheral
    "Okapi":   Device("Okapi",   4096, "m1284p", 0xFF),   # logger; not an I2C peripheral
    "Apis":    Device("Apis",    1024, "m328p",  0x41),   # 'A'
    "Haar":    Device("Haar",    1024, "m328p",  0x48),   # 'H'
    "Walrus":  Device("Walrus",  1024, "m328p",  0x57),   # 'W'
    "Libelle": Device("Libelle", 1024, "m328p",  0x4C),   # 'L' — address clash TBD
}
