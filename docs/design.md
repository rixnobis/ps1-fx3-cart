# ps1-fx3-cart design notes

## Requirements
- PIO bus to the FX3: D0-D15, A0-A1 (A2-A3 spare), /CS0, /RD, /WR0, /WR1, DREQ5, DACK5,
  /INT10, /RESET, SYSCLK1 (33.8688 MHz, runs regardless of /RESET), SBEN.
- Switch Board selects: /CS5 + /IN2 (CD-ROM controller), /CS2 (BIOS).
- I2S into the SPU mixer: the console drives BCLK/LRCK, the cart drives SDIN. The FX3's I2S
  block is master-only, so SDIN comes from GPIF II or a part slaved to the console's clocks.
- Optional BIOS NOR flash behind /CS2, TSOP48, not fitted by default: /CE = /CS2, /OE = /RD,
  /WE = /WR0, A0-A18 and D0-D7 from the PIO bus, no flash signal to the FX3. Programmed by
  host code on the console running from RAM. BIOS-region writes do reach the bus: the
  DTL-H2700's own flasher JEDEC-programs a flash in the BIOS window. Before writing, it sets
  the BIOS ROM delay/size register 1F801010 to 0x142433, and it restores the old value
  afterwards. The cart's host flasher copies that sequence. The S29AL016J in byte mode takes
  its unlock cycles at byte offsets 0xAAA/0x555 (PIO A0 on the flash's A-1); the full 2 MB
  needs A0-A20 and a BIOS window enlarged past the 19-bit default.
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
- The flash's byte-mode command addresses against the PIO address lines.
- Which FX3 pins the boot ROM touches in the chosen boot mode (the reset gate pin must be one
  it leaves tristated with no pull-down).
- Current budget of the PIO 3.3 V rail (pins 17/51) against the FX3's worst case.

## FX3 pin map (tools/gen_sch.py PIO_GPIO)
GPIF II in 16-bit mode, clocked by the console: PCLK (GPIO16) = SYSCLK1.

| FX3 | Signal | FX3 | Signal |
|---|---|---|---|
| GPIO0-15 (DQ0-15) | D0-D15 | GPIO33 | reset hold gate (boot ROM: tristate) |
| GPIO16 (PCLK) | SYSCLK1 | GPIO34 | /RESET sense |
| GPIO17 (CTL0) | /CS0 | GPIO35 | /INT10 |
| GPIO18 (CTL1) | /RD | GPIO36 | /IN2 (CD-ROM IRQ, Switch Board) |
| GPIO19 (CTL2) | /WR0 | GPIO37 | SBEN |
| GPIO20 (CTL3) | /WR1 | GPIO38 | A3 |
| GPIO21-22 (CTL4-5) | A0, A1 | GPIO39 | /CS2 sense (flash access, read only) |
| GPIO23 (CTL6) | DACK5 | GPIO50-52 | status LED |
| GPIO24 (CTL7) | DREQ5 | GPIO55-56 | debug UART |
| GPIO25 (CTL8) | /CS5 (CD-ROM, Switch Board) | GPIO58-59 | I2C boot EEPROM |
| GPIO26-28 (CTL9-11) | I2S BCLK, LRCK (in), SDIN (out) | GPIO30-32 | PMODE straps |
| GPIO29 (CTL12) | A2 | | |

The I2S lines sit on GPIF control pins so a GPIF state can sample BCLK/LRCK and drive SDIN
in the same machine that serves the bus. A slaved shift-register fallback can be wired from
the same nets if that proves too tight. None of the lines the boot ROM drives (GPIO42, 45,
51, 53 and 55, AN76405 Table 30) carries a console-facing signal. GPIO51 lights the green LED
during boot.

## Power
The cart runs from the console's PIO 3.3 V rail (pins 17/51; 3.3 V nominal, wanders to 3.5 V),
like the existing PIO carts, which also take their logic supply from the port and keep USB VBUS
separate. All FX3 I/O domains (VIO1-VIO5) and CVDDQ sit on it directly: the FX3 datasheet gives
1.7-3.6 V operating for every VIO, so the bus needs no level translation, and the FX3 can never
be powered from the bus pins while the console is off, because both come from the same rail. The
1.2 V core and USB 3 supplies come from a buck that starts at 3.3 V in. USB VBUS goes only to the
FX3's VBUS detect. With the console off the cart is dead and the host sees no device. With USB
unplugged the cart still runs and still holds the console in reset until its firmware boots
from the I2C EEPROM.

## Parts checked against JLC stock (tools/jlc_stock.py)
- 1.2 V core buck from the 3.3 V rail: TLV62569DBVR (2.5-5.5 V in, 2 A, SOT-23-5), C141836, deep stock.
- USB 3 connector, open: Hirose ZX360D-B-10P USB 3.0 Micro-B (C598201, in stock) needs no lane
  mux. A USB-C 24-pin receptacle (GCT USB4110-GF-A, C5143397, in stock) needs an orientation
  mux for the FX3's single SuperSpeed lane, e.g. HD3SS3220 (C165155, in stock): one more
  WQFN-30, CC handling, and a second differential crossing.
