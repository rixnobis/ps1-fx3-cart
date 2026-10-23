# ps1-fx3-cart design notes

## Requirements
- PIO bus to the FX3: D0-D15, A0-A1 (A2-A3 spare), /CS0, /RD, /WR0, /WR1, DREQ5, DACK5,
  /INT10, /RESET, SYSCLK1 (33.8688 MHz, runs regardless of /RESET), SBEN.
- Switch Board selects: /CS5 + /IN2 (CD-ROM controller), /CS2 (BIOS).
- I2S into the SPU mixer: the console drives BCLK/LRCK, the cart drives SDIN. The FX3's I2S
  block is master-only, so SDIN comes from GPIF II or a part slaved to the console's clocks.
- Optional BIOS NOR flash behind /CS2, TSOP48, not fitted by default: /CE = /CS2, /OE = /RD,
  /WE = /WR0, A0-A18 and D0-D7 from the PIO bus, no flash signal to the FX3. Programmed by
  host code on the console running from RAM.
- Reset: the cart holds the console in reset until FX3 firmware runs. An N-MOSFET pulls PIO
  /RESET to GND, its gate pulled up to the cart's 3.3 V and driven by one FX3 pin (tristated
  in the boot ROM, so the console stays held); firmware drives it low to release. A second FX3
  pin senses /RESET through a series resistor.
- Defaults for the unconfigured window, by external resistors: SBEN low, /IRQ10 and /IRQ2
  pulled up, DREQ5 inactive.

## Layout rules
Connector on the back of the PCB, components facing away from the console, back-side parts
under the top-of-shell line, USB connector on the right side past the shell line, an STL case
ordered with the boards.

## Open before the schematic is final
- Whether a CPU write to the BIOS region asserts /CS2 and /WR0 on the PIO bus.
- The flash's byte-mode command addresses against the PIO address lines.
- Which FX3 pins the boot ROM touches in the chosen boot mode (the reset gate pin must be one
  it leaves tristated with no pull-down).
- Supply: which PIO rail powers the cart (3.3 V nominal that reads up to 3.5 V, or +7.5 V
  through a buck), and its current budget.
