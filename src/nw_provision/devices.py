from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    name: str               # up to 7 ASCII chars; written to Page 0 bytes 0x01–0x07
    eeprom_size: int        # total EEPROM bytes; Page 0 lives at eeprom_size - 32
    avrdude_part: str       # avrdude -p argument
    i2c_address: int        # default I2C address written to Page 0 byte 0x1F;
                            # 0xFF = not a peripheral / use device default
    board_type_high: int    # high byte of board_type (Page 0 offset 0x10);
                            # from NW-Registry board_types.csv — NOT always ASCII of name[0]


DEVICES = {
    #           name       eeprom  part      i2c    bt_high
    "Margay":  Device("Margay",  4096, "m1284p", 0xFF,  0x4D),  # 'M' — follows ASCII scheme
    "Okapi":   Device("Okapi",   4096, "m1284p", 0xFF,  0x99),  # legacy Resnik code
    "Apis":    Device("Apis",    1024, "m328p",  0x41,  0x6C),  # legacy "Project Symbiont Lidar"
    "Haar":    Device("Haar",    1024, "m328p",  0x48,  0x48),  # 'H' — follows ASCII scheme
    "Walrus":  Device("Walrus",  1024, "m328p",  0x57,  0x57),  # 'W' — follows ASCII scheme
    "Libelle": Device("Libelle", 1024, "m328p",  0x4C,  0x23),  # legacy Dyson SW code
}
