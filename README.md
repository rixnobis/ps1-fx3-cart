# ps1-fx3-cart

A PlayStation expansion-port (PIO) cartridge built around a Cypress/Infineon FX3
(CYUSB3014) USB 3 controller. Every PIO signal the cart needs goes to the FX3's GPIF II
or GPIO pins, so the link protocol, DMA5, INT10, the I2S audio input and a CD-ROM
controller personality are firmware questions rather than board revisions. An optional
NOR flash behind the BIOS chip select (Switch Board) is programmed by code running on
the console.

Status: schematic in progress. Design notes and open questions: `docs/design.md`.

The board shares its FX3 core (power, clock, boot EEPROM, USB 3 routing) with
[ps1-av-capture](https://github.com/rixnobis/ps1-av-capture).
