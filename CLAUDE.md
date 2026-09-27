# NW-Provision

Write a Schema 1 identity and calibration into a device's EEPROM: Page 0 (identity, CRC, I2C address) and Page 1 (calibration), as `NW-Device-Specification` defines them. Replaces the old `MargaySetup.ino`, and is the only thing that should write those pages.

## Standards

Follow the NW standards in the root `CLAUDE.md` one level above `github/`. The page layouts are normative in [NW-Device-Specification](https://github.com/NorthernWidget/NW-Device-Specification); this repository implements them and never invents them.

## Working rules

- The stored half is the **top 64 bytes** of EEPROM, in bus order: Margay 0x0FC0, ATtiny1634 0x00C0, ATtiny841 0x01C0. `build_page0` and the Page 1 builders produce exactly those bytes.
- A change to a page layout is a change to the **specification first**, then here, then the firmware and the library that read it. Never the other way round.
- The test suite is the contract: run it before every commit, and add a case for every layout change.
- Page images built here are what `NW-Sim` feeds its simulated devices, so a layout error shows up as a simulated device that will not identify.
- Writing to hardware needs a board in hand and Andy's word; building an image does not.

## Hard rule

**Never** create a git tag, GitHub release, push to a shared remote, or write to an attached device unless explicitly asked in the current message. If in doubt, ask.
