from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    name: str               # up to 7 ASCII chars; written to Page 0 bytes 0x01–0x07
    mcu: str                # human-readable MCU name, e.g. "ATmega1284P"
    eeprom_size: int        # total EEPROM bytes; Page 0 lives at eeprom_size - 32
                            # 0 = no MCU / not yet defined
    avrdude_part: str       # avrdude -p argument; "" = no MCU / not yet defined
    i2c_address: int        # default I2C address written to Page 0 byte 0x1F;
                            # 0xFF = not a peripheral / use device default
    board_type_high: int    # high byte of board_type (Page 0 offset 0x10);
                            # from NW-Registry board_types.csv — NOT always ASCII of name[0]
    has_mcu: bool = True    # False = no onboard MCU; avrdude write not possible


DEVICES = {
    #           name       mcu             eeprom  part      i2c    bt_high  has_mcu
    "Margay":  Device("Margay",  "ATmega1284P", 4096, "m1284p", 0xFF,  0x4D),
    "Okapi":   Device("Okapi",   "ATmega1284P", 4096, "m1284p", 0xFF,  0x99),
    "Apis":    Device("Apis",    "ATtiny1634",   256, "t1634",  0x41,  0x6C),
    "Haar":    Device("Haar",    "ATtiny1634",   256, "t1634",  0x48,  0x48),
    "Walrus":  Device("Walrus",  "ATtiny1634",   256, "t1634",  0x57,  0x57),
    "Libelle": Device("Libelle", "ATtiny841",    512, "t841",   0x4C,  0x23),
    "Liasis":  Device("Liasis",  "",               0, "",       0xFF,  0x24, False),
}
