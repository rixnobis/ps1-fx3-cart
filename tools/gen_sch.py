#!/usr/bin/env python3
"""Generate the ps1-fx3-cart schematic: a root sheet plus its sub-sheets.

Nets are carried by global labels on every pin stub, so a net name is the same on every
sheet. Run tools/build.sh to regenerate, run ERC and export the PDF.
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sch_lib as L  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "tools" / "pins"
ROOT_UUID = "2f6a9c51-7d3e-4b08-9e1a-6c4d2b8f0a11"

# ---------------------------------------------------------------- footprints, parts
FP = {
    "R0402": "Resistor_SMD:R_0402_1005Metric",
    "C0402": "Capacitor_SMD:C_0402_1005Metric",
    "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric",
    "FB0603": "Inductor_SMD:L_0603_1608Metric",
    "L4030": "Inductor_SMD:L_Sunlord_SWPA4030S",
    "SOT23-5": "Package_TO_SOT_SMD:SOT-23-5",
    "SOT23": "Package_TO_SOT_SMD:SOT-23",
    "SOT23-6": "Package_TO_SOT_SMD:SOT-23-6",
    "USBMB3": "fx3-cart:USB-SMD_ZX360D-B-10P-30",  # LCSC C598201 land pattern, shell pads named SH
    "BUCK": "fx3-cart:SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR",
    "FX3": "fx3-cart:BGA-121_L10.0-W10.0-R11-C11-P0.80-TL",
    "PIOCONN": "fx3-cart:PIOCONN",       # tools/eagle_pkg.py from pcsx-redux hardware/pixel.lbr
    "XTAL3225": "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    "TSOP48": "Package_SO:TSOP-I-48_18.4x12mm_P0.5mm",   # TS048, 12 x 20 mm
    "SOIC8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "USON10": "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
    "LED0603": "LED_SMD:LED_0603_1608Metric",
    "LED1615RGB": "fx3-cart:LED-ARRAY-SMD_4P-L1.6-W1.5-BR_XL-1615RGBC-RF",
    "JTAG": "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD",
    "HDR3": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    "HDR2": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    "SW": "Button_Switch_SMD:SW_SPST_TL3342",
    "MH": "MountingHole:MountingHole_3.2mm_M3",
}

# LCSC numbers: tools/check_lcsc.py reads each one back from JLC and checks the
# description against the value before the BOM is trusted.
LCSC_PASSIVE = {
    ("R0402", "22"): "C25092", ("R0402", "75"): "C25133", ("R0402", "200 1%"): "C25087",
    ("R0402", "1k"): "C11702", ("R0402", "100"): "C25076", ("R0402", "470"): "C25117", ("R0402", "1.5k"): "C25867", ("R0402", "2k"): "C4109",
    ("R0402", "2.2k"): "C25879", ("R0402", "5.1k"): "C25905", ("R0402", "6.04k 1%"): "C97819",
    ("R0402", "10k"): "C25744", ("R0402", "22.6k 1%"): "C26960", ("R0402", "33.2k 1%"): "C122548",
    ("R0402", "5.76k 1%"): "C5153969", ("R0402", "100k"): "C25741", ("R0402", "1M"): "C26083",
    ("C0402", "33p"): "C1562", ("C0402", "6.8p"): "C1576", ("C0402", "12p"): "C1547", ("C0402", "330p"): "C13533",
    ("C0402", "1n"): "C1523", ("C0402", "2.2n"): "C1531", ("C0402", "4.7n"): "C1538",
    ("C0402", "10n"): "C15195", ("C0402", "100n"): "C1525", ("C0402", "1u"): "C52923",
    ("C0603", "2.2u"): "C23630", ("C0603", "10u"): "C19702", ("C0805", "22u"): "C45783",
    ("FB0603", "600R"): "C108301", ("L4030", "2.2u"): "C36409",
}

# ---------------------------------------------------------------- symbols
STK = {}


def stk(lib, name):
    return STK.setdefault((lib, name), L.stock(lib, name))


def table(name):
    return [(r[0], r[1]) for r in csv.reader(open(PINS / f"{name}.csv"))][1:]


POWER_NAMES = re.compile(r"^(VDD|VSS|AVDD|AVSS|U3\w+VDDQ|U3VSSQ|CVDDQ|VIO\d|VBUS|VBATT|"
                         r"A33VDD|A33GND|AGND|DVDD|DGND|GND|IOVDD|IOGND|PLL_AVDD|PLL_AGND|NSUB|"
                         r"VCCC|VCCP\d|VCCX|AGNDC|AGNDP|AGNDX|DGNDU)$")


def et(name):
    return "power_in" if POWER_NAMES.match(name) else "passive"


def build_fx3():
    rows = table("fx3")
    gpio = lambda b, n: (b, n, et(n))  # noqa: E731
    by = {n: [] for _, n in rows}
    for b, n in rows:
        by.setdefault(n, []).append(b)
    num = lambda n: int(re.search(r"\[(\d+)\]", n).group(1)) if "[" in n else -1  # noqa: E731
    gpif = sorted([(b, n) for b, n in rows if n.startswith("GPIO[") and num(n) <= 45], key=lambda r: num(r[1]))
    gpif.append([(b, n) for b, n in rows if n == "INT#"][0])
    misc_names = [n for _, n in rows if not n.startswith("GPIO[") and not POWER_NAMES.match(n)
                  and n != "INT#" or (n.startswith("GPIO[") and num(n) > 45)]
    misc = [(b, n) for b, n in rows if n in misc_names]
    pwr = [(b, n) for b, n in rows if POWER_NAMES.match(n)]
    assert len(gpif) + len(misc) + len(pwr) == 121, (len(gpif), len(misc), len(pwr))
    half = (len(gpif) + 1) // 2
    u1 = {"left": [gpio(b, n) for b, n in gpif[:half]], "right": [gpio(b, n) for b, n in gpif[half:]]}
    misc.sort(key=lambda r: (r[1].startswith("GPIO") or r[1].startswith("I2C"), r[1]))
    h2 = (len(misc) + 1) // 2
    u2 = {"left": [gpio(b, n) for b, n in misc[:h2]], "right": [gpio(b, n) for b, n in misc[h2:]]}
    pos = [(b, n) for b, n in pwr if not re.search("VSS|GND", n)]
    neg = [(b, n) for b, n in pwr if re.search("VSS|GND", n)]
    pos.sort(key=lambda r: r[1])
    u3 = {"left": [gpio(b, n) for b, n in pos], "right": [gpio(b, n) for b, n in neg]}
    return L.custom("CYUSB3014-BZXI", [u1, u2, u3], footprint=FP["FX3"])


# PIO connector, console rear-view numbering: 1-34 one side, 35-68 the other (psx-spx expansion
# port pinout; the pad numbers of pixel.lbr's PIOCONN carry the same signals).
# pin: (symbol pin name, net). DREQ5 and DACK5 are active high (psx-spx), the rest as named.
PIO_PINS = {2: ("~{RESET}", "PIO_RESETn"), 3: ("DREQ5", "PIO_DREQ5"), 36: ("DACK5", "PIO_DACK5"),
            4: ("~{CS0}", "PIO_CS0n"), 5: ("SBEN", "PIO_SBEN"), 39: ("~{CS2}", "PIO_CS2n"),
            30: ("~{RD}", "PIO_RDn"), 64: ("~{WR0}", "PIO_WR0n"), 38: ("~{WR1}", "PIO_WR1n"),
            37: ("~{IRQ10}", "PIO_INT10n"), 31: ("~{IRQ2}", "PIO_IN2n"), 65: ("~{CS5}", "PIO_CS5n"),
            32: ("SYSCLK1", "PIO_SYSCLK1"), 33: ("BCLK", "PIO_I2S_BCLK"), 66: ("LRCK", "PIO_I2S_LRCK"),
            67: ("SDIN", "PIO_I2S_SDIN"), 17: ("+3.3V", "+3V3"), 51: ("+3.3V", "+3V3"),
            18: ("+7.5V", None), 52: ("+7.5V", None)}
for _p in (1, 35, 34, 68, 16, 50, 19, 53):
    PIO_PINS[_p] = ("GND", "GND")
for _i, _p in enumerate((6, 40, 7, 41, 8, 42, 9, 43, 10, 44, 11, 45, 12, 46, 13, 47)):
    PIO_PINS[_p] = (f"D{_i}", f"PIO_D{_i}")
for _i, _p in enumerate((14, 48, 15, 49, 20, 54, 21, 55, 22, 56, 23, 57, 24, 58, 25, 59, 26, 60,
                         27, 61, 28, 62, 29, 63)):
    PIO_PINS[_p] = (f"A{_i}", f"PIO_A{_i}" if _i <= 20 else None)   # A21-A23 unused
assert sorted(PIO_PINS) == list(range(1, 69))


def build_pio():
    side = lambda r: [(str(p), PIO_PINS[p][0], "passive") for p in r]  # noqa: E731
    return L.custom("PIO_68", [{"left": side(range(1, 35)), "right": side(range(35, 69))}],
                    ref="J", footprint=FP["PIOCONN"])


# S29AL016J TS048 pinout, datasheet 002-00777 Figure 1. In byte mode (BYTE# low) DQ15 is the
# LSB address A-1 and DQ8-DQ14 float.
S29_PINS = {1: "A15", 2: "A14", 3: "A13", 4: "A12", 5: "A11", 6: "A10", 7: "A9", 8: "A8", 9: "A19",
            10: "NC", 11: "WE#", 12: "RESET#", 13: "NC", 14: "WP#", 15: "RY/BY#", 16: "A18", 17: "A17",
            18: "A7", 19: "A6", 20: "A5", 21: "A4", 22: "A3", 23: "A2", 24: "A1", 25: "A0", 26: "CE#",
            27: "VSS", 28: "OE#", 29: "DQ0", 30: "DQ8", 31: "DQ1", 32: "DQ9", 33: "DQ2", 34: "DQ10",
            35: "DQ3", 36: "DQ11", 37: "VCC", 38: "DQ4", 39: "DQ12", 40: "DQ5", 41: "DQ13", 42: "DQ6",
            43: "DQ14", 44: "DQ7", 45: "DQ15/A-1", 46: "VSS", 47: "BYTE#", 48: "A16"}


def build_s29():
    by = {n: p for p, n in S29_PINS.items() if n not in ("NC", "VSS")}
    t = lambda n: "power_in" if n in ("VCC", "VSS") else "passive"  # noqa: E731
    ov = lambda n: "~{%s}" % n[:-1] if n.endswith("#") else n  # noqa: E731
    left = ["DQ15/A-1"] + [f"A{i}" for i in range(20)]
    right = ([f"DQ{i}" for i in range(15)] + ["CE#", "OE#", "WE#", "BYTE#", "RESET#", "WP#", "RY/BY#", "VCC"])
    L_ = [(str(by[n]), ov(n), t(n)) for n in left]
    R_ = [(str(by[n]), ov(n), t(n)) for n in right]
    R_ += [("27", "VSS", "power_in"), ("46", "VSS", "power_in"), ("10", "NC", "no_connect"),
           ("13", "NC", "no_connect")]
    return L.custom("S29AL016J70TFI020", [{"left": L_, "right": R_}], footprint=FP["TSOP48"])


FX3 = build_fx3()
PIO = build_pio()
S29 = build_s29()

# ---------------------------------------------------------------- sheets and placement
SHEETS = {k: L.Sheet(*v) for k, v in {
    "pio": ("PIO", "pio.kicad_sch", "PIO connector, reset hold, defaults", "A3"),
    "flash": ("Flash", "flash.kicad_sch", "Optional BIOS NOR flash (not fitted)", "A3"),
    "fx3": ("FX3", "fx3.kicad_sch", "FX3 USB 3 bridge", "A2"),
    "usb": ("USB", "usb.kicad_sch", "USB 3 connector (provisional: Micro-B)", "A3"),
    "power": ("Power", "power.kicad_sch", "1.2 V buck from the PIO 3.3 V rail", "A3"),
}.items()}
for s in SHEETS.values():
    s.path = f"/{ROOT_UUID}/{s.uuid}"
    s.cx, s.cy, s.rowh = 30.0, 45.0, 0.0
    s.bx0, s.bw, s.btop, s.bbot = 20.0, 0.0, 30.0, 30.0   # current block
    s.shx, s.shy, s.shh = 20.0, 30.0, 0.0                 # current shelf of blocks

PAPER = {"A3": (420.0, 297.0), "A2": (594.0, 420.0), "A1": (841.0, 594.0)}
REFS = {"U": 1, "J": 2}  # U1 FX3, J1 PIO connector, J2 USB are assigned by hand
ALL = []  # (ref, sym, unit, nets, value)
USED = set()


def nextref(p):
    REFS[p] = REFS.get(p, 0) + 1
    return f"{p}{REFS[p]}"


def heading(sheet, s, width=175.0):
    """Start a block: blocks sit side by side on a shelf, a new shelf when the page is full."""
    import textwrap
    sh = SHEETS[sheet]
    sh.bbot = max(sh.bbot, sh.cy + sh.rowh)
    sh.shh = max(sh.shh, sh.bbot - sh.shy)
    nx = sh.bx0 + sh.bw + (8.0 if sh.bw else 0.0)
    if nx + width > PAPER[sh.paper][0] - 20:
        sh.shy, sh.shh, nx = sh.shy + sh.shh + 6.0, 0.0, 20.0
    sh.bx0, sh.bw = nx, width
    lines = textwrap.wrap(s, int(width / 1.75))
    sh.text("\n".join(lines), nx, sh.shy + 4.0, 1.8)
    sh.cx, sh.cy, sh.rowh = nx, sh.shy + 4.0 + 3.2 * len(lines) + 2.0, 0.0
    sh.bbot = sh.cy


def put(sheet, sym, prefix, value, nets, fp="", unit=1, lcsc=None, dnp=False, ref=None, note=None):
    sh = SHEETS[sheet]
    x0, y0, x1, y1 = sym.bbox(unit)
    angs = {p[2] for v in sym.pins.values() for p in v if p[3] in (unit, 0)}
    margin = 24.0 if angs & {0.0, 180.0} else 4.0       # side labels need room
    vmargin = 16.0 if angs & {90.0, 270.0} else 5.0     # labels above / below
    w, h = (x1 - x0) + 2 * margin, (y1 - y0) + 2 * vmargin
    if sh.cx + w > sh.bx0 + max(sh.bw, w) + 0.01:
        sh.cx, sh.cy, sh.rowh = sh.bx0, sh.cy + sh.rowh, 0.0
    x, y = sh.cx + margin - x0, sh.cy + vmargin + y1
    x, y = round(x / 2.54) * 2.54, round(y / 2.54) * 2.54
    ref = ref or nextref(prefix)
    assert ref not in USED or unit > 1, f"duplicate reference {ref}"
    USED.add(ref)
    if lcsc is None and fp in ("R0402", "C0402", "C0603", "C0805", "FB0603", "L4030"):
        lcsc = LCSC_PASSIVE[(fp, value)]
    fields = (("LCSC", lcsc),) if lcsc else ()
    if note:
        fields += (("Note", note),)
    sh.place(sym, ref, value, x, y, {str(k): v for k, v in nets.items()}, unit=unit,
             footprint=FP.get(fp, fp), fields=fields, dnp=dnp, path=sh.path,
             in_bom=sym.lib_id != "Mechanical:MountingHole" and not sym.lib_id.startswith("power:"))
    sh.cx += w
    sh.rowh = max(sh.rowh, h)
    ALL.append((ref, sym, unit, nets, value))
    return ref


R = lambda: stk("Device", "R")  # noqa: E731
C = lambda: stk("Device", "C")  # noqa: E731


def res(sheet, value, a, b, fp="R0402", **kw):
    return put(sheet, R(), "R", value, {1: a, 2: b}, fp, **kw)


def cap(sheet, value, a, b="GND", fp=None, **kw):
    fp = fp or ("C0805" if value == "22u" else "C0603" if value in ("10u", "2.2u") else "C0402")
    return put(sheet, C(), "C", value, {1: a, 2: b}, fp, **kw)


def bead(sheet, a, b):
    return put(sheet, stk("Device", "FerriteBead_Small"), "FB", "600R", {1: a, 2: b}, "FB0603")


# ================================================================ PIO sheet
heading("pio", "PIO expansion port (CN103), pin numbers as psx-spx (console rear view). On a stock "
        "console pin 5 (SBEN) and pin 39 (/CS2) are GND and pins 31/65 are NC; they carry SBEN, /CS2, "
        "/IRQ2 and /CS5 only with a Switch Board mod. The 3.3 V pins feed the whole cart; 7.5 V and "
        "A21-A23 are unused.", width=150.0)
put("pio", PIO, "J", "PIO", {p: n for p, (_, n) in PIO_PINS.items()}, "PIOCONN", ref="J1")
heading("pio", "Reset hold: Q1 pulls PIO /RESET low while its gate is high. The gate pin GPIO33 is "
        "tristated by the boot ROM (AN76405 Table 30), so the 1k pull-up holds the console in reset "
        "until FX3 firmware drives GPIO33 low. Sizing: the FX3 can put a 10k pull-down on any pin "
        "(datasheet I/O states), and AN76405 does not say the boot ROM's tristate excludes it; "
        "1k against 10k still gives 3.3 V x 10/11 = 3.0 V on the gate, above the 2N7002's 2.5 V "
        "maximum VGS(th). Released, GPIO33 sinks 3.3 mA, under the IOL of quarter drive (3.96 mA "
        "even at VIO 2.5 V, datasheet Table 9). "
        "GPIO34 senses /RESET through 1k: 3.3 mA at most if it is ever driven as an output, and an "
        "internal 10k pull-down still reads high (3.0 V).", width=150.0)
# Gate pull-up: 1k, not 10k. A 10k pull-up against a possible internal 10k pull-down would leave
# the gate at 1.65 V, inside the 2N7002's 1.0-2.5 V VGS(th) spread; 1k leaves 3.0 V (3.3 V rail).
put("pio", stk("Transistor_FET", "2N7002"), "Q", "2N7002", {1: "RST_HOLD", 2: "GND", 3: "PIO_RESETn"},
    "SOT23", lcsc="C8545")
res("pio", "1k", "RST_HOLD", "+3V3")
res("pio", "1k", "PIO_RESETn", "RST_SENSE")
heading("pio", "/CS2 sense: GPIO39 reads pin 39 through 1k. Pin 39 is GND on a stock console, so "
        "GPIO39 misdriven high sinks 3.3 mA instead of shorting the pin.", width=150.0)
res("pio", "1k", "PIO_CS2n", "PIO_CS2n_SENSE")
heading("pio", "Defaults while the FX3 is unconfigured: SBEN low (no Switch Board takeover), /IRQ10 and "
        "/IRQ2 high (inactive), DREQ5 low (inactive; DREQ/DACK are active high).", width=150.0)
res("pio", "10k", "PIO_SBEN", "GND")
res("pio", "10k", "PIO_INT10n", "+3V3")
res("pio", "10k", "PIO_IN2n", "+3V3")
res("pio", "10k", "PIO_DREQ5", "GND")

# ================================================================ flash sheet
heading("flash", "Optional BIOS NOR flash, NOT FITTED by default. S29AL016J (2 MB) in byte mode: BYTE# "
        "low, PIO A0 on DQ15/A-1, PIO A1-A20 on flash A0-A19, so flash byte address = PIO byte address "
        "and the unlock cycles land at BIOS offsets 0xAAA/0x555. /CE = /CS2, /OE = /RD, /WE = /WR0, "
        "D0-D7 shared with the FX3. No flash signal goes to the FX3 (GPIO39 only senses /CS2). The "
        "full 2 MB needs the BIOS window (1F801010) enlarged to 21 address bits. Fit only with the "
        "Switch Board /CS2 mod: on a stock console pin 39 is GND, which would enable the flash on "
        "every /RD. RESET# follows the console reset; WP# high; RY/BY# unused (firmware polls DQ7/DQ6).",
        width=150.0)
_fl = {25: "PIO_A1", 45: "PIO_A0", 26: "PIO_CS2n", 28: "PIO_RDn", 11: "PIO_WR0n", 47: "GND",
       12: "PIO_RESETn", 14: "+3V3", 15: None, 37: "+3V3", 27: "GND", 46: "GND", 10: None, 13: None}
for _p, _n in S29_PINS.items():
    if _n.startswith("A") and _n[1:].isdigit():
        _fl[_p] = f"PIO_A{int(_n[1:]) + 1}"
    elif _n.startswith("DQ") and _n[2:].isdigit():
        _fl[_p] = f"PIO_D{_n[2:]}" if int(_n[2:]) <= 7 else None
assert sorted(_fl) == list(range(1, 49))
put("flash", S29, "U", "S29AL016J70TFI020", _fl, "TSOP48", lcsc="C914935", dnp=True)
cap("flash", "100n", "+3V3", dnp=True)

# ================================================================ FX3 sheet
# FX3 GPIO -> PIO net. GPIF II in 16-bit mode: DQ[15:0] = D15..D0, PCLK = SYSCLK1 (the bus runs
# synchronous to the console's 33.8688 MHz clock), the strobes, selects, A0-A1, DREQ5/DACK5 and
# the console-clocked I2S on CTL[0..12]. VIO2 GPIOs carry the slow lines. The reset gate is on
# GPIO33, which the boot ROM leaves tristated in both USB and I2C boot (AN76405 Table 30), and
# nothing here sits on GPIO42/45/51/53/55, which the boot ROM drives.
PIO_GPIO = {16: "PIO_SYSCLK1",
            17: "PIO_CS0n", 18: "PIO_RDn", 19: "PIO_WR0n", 20: "PIO_WR1n", 21: "PIO_A0", 22: "PIO_A1",
            23: "PIO_DACK5", 24: "PIO_DREQ5", 25: "PIO_CS5n", 26: "PIO_I2S_BCLK", 27: "PIO_I2S_LRCK",
            28: "PIO_I2S_SDIN", 29: "PIO_A2",
            33: "RST_HOLD", 34: "RST_SENSE", 35: "PIO_INT10n", 36: "PIO_IN2n", 37: "PIO_SBEN",
            38: "PIO_A3", 39: "PIO_CS2n_SENSE",
            30: "FX3_PMODE0", 31: "FX3_PMODE1", 32: "FX3_PMODE2",
            50: "LED_R", 51: "LED_G", 52: "LED_B", 55: "FX3_UART_TX", 56: "FX3_UART_RX"}
fx3_nets = {}
for b, n in table("fx3"):
    g = re.match(r"^GPIO\[(\d+)\]$", n)
    if g:
        k = int(g.group(1))
        fx3_nets[b] = f"PIO_D{k}" if k <= 15 else PIO_GPIO.get(k)
        continue
    fx3_nets[b] = {
        "I2C_GPIO[58]": "I2C_SCL", "I2C_GPIO[59]": "I2C_SDA", "INT#": None, "NC": None,
        "CLKIN": None, "CLKIN_32": None, "OTG_ID": None, "TRST#": None,
        "FSLC[0]": "FX3_FSLC", "FSLC[1]": "FX3_FSLC", "FSLC[2]": "FX3_FSLC",
        "RESET#": "FX3_RESETn", "XTALIN": "FX3_XI", "XTALOUT": "FX3_XO",
        "TDI": "FX3_TDI", "TDO": "FX3_TDO", "TMS": "FX3_TMS", "TCK": "FX3_TCK",
        "DP": "USB3_DP", "DM": "USB3_DM", "SSRXM": "USB3_RXN", "SSRXP": "USB3_RXP",
        "SSTXM": "USB3_TXN_C", "SSTXP": "USB3_TXP_C", "R_USB2": "FX3_RUSB2", "R_USB3": "FX3_RUSB3",
        "VBUS": "VBUS", "VBATT": "VBUS", "VDD": "+1V2", "AVDD": "FX3_AVDD",
        "U3TXVDDQ": "FX3_U3TX", "U3RXVDDQ": "FX3_U3RX", "CVDDQ": "FX3_CVDDQ",
        "VIO1": "+3V3", "VIO2": "+3V3", "VIO3": "+3V3", "VIO4": "+3V3", "VIO5": "+3V3",
        "VSS": "GND", "AVSS": "GND", "U3VSSQ": "GND",
    }[n]
heading("fx3", "CYUSB3014. GPIF II in 16-bit mode takes the PIO bus: DQ[15:0]=D15..D0, PCLK=SYSCLK1, "
        "strobes, selects, A0-A2, DREQ5/DACK5 and I2S on CTL[0..12] (VIO1). Slow lines on VIO2 GPIO33-39. "
        "All VIO on the PIO 3.3 V rail. Map: PIO_GPIO in tools/gen_sch.py, docs/design.md.")
for u in (1, 2, 3):
    put("fx3", FX3, "U", "CYUSB3014-BZXI", {k: v for k, v in fx3_nets.items()
                                             if any(pp[3] == u for pp in FX3.pins[k])},
        "FX3", unit=u, lcsc="C57294", ref="U1")
heading("fx3", "19.2 MHz crystal, FSLC[2:0]=000 through one 10k (AN70707 Figure 9). No series "
        "resistor on the crystal (AN70707). Load caps sized for a 12 pF crystal with ~5 pF stray.")
put("fx3", stk("Device", "Crystal_GND24"), "Y", "19.2MHz", {1: "FX3_XI", 3: "FX3_XO", 2: "GND", 4: "GND"},
    "XTAL3225", lcsc="C411225")
cap("fx3", "12p", "FX3_XI")
cap("fx3", "12p", "FX3_XO")
res("fx3", "10k", "FX3_FSLC", "GND")
heading("fx3", "Boot: PMODE F1F = I2C EEPROM, USB fallback (AN70707 Table 9). 10k up/down footprints "
        "on every PMODE pin, only PMODE1 up fitted. Jumper JP1 pulls PMODE0 high = F11, USB boot only.")
for i in range(3):
    res("fx3", "10k", f"FX3_PMODE{i}", "+3V3", dnp=(i != 1))
    res("fx3", "10k", f"FX3_PMODE{i}", "GND", dnp=True)
put("fx3", stk("Connector_Generic", "Conn_01x02"), "JP", "USB_BOOT", {1: "FX3_PMODE0", 2: "FX3_PMODE0_UP"}, "HDR2")
res("fx3", "1k", "FX3_PMODE0_UP", "+3V3")
heading("fx3", "Reset: RC holds RESET# low > 1 ms after power (tRPW 1 ms, tRR 5 ms with a crystal); "
        "button and the JTAG header can also pull it.")
res("fx3", "10k", "FX3_RESETn", "FX3_CVDDQ")
cap("fx3", "1u", "FX3_RESETn")
put("fx3", stk("Switch", "SW_Push"), "SW", "RESET", {1: "FX3_RESETn", 2: "GND"}, "SW", lcsc="C318884")
heading("fx3", "I2C: boot EEPROM, 2k pull-ups to VIO5 (AN70707). "
        "24LC1025 A2 must be tied high; A1:A0 = 00.")
put("fx3", stk("Memory_EEPROM", "24LC1025"), "U", "24LC1025-I/SN", {
    1: "GND", 2: "GND", 3: "+3V3", 4: "GND", 5: "I2C_SDA", 6: "I2C_SCL", 7: "GND", 8: "+3V3"},
    "SOIC8", lcsc="C615697")
put("fx3", stk("Memory_EEPROM", "24LC1025"), "U", "24LC1025-I/SN", {
    1: "+3V3", 2: "GND", 3: "+3V3", 4: "GND", 5: "I2C_SDA", 6: "I2C_SCL", 7: "GND", 8: "+3V3"},
    "SOIC8", lcsc="C615697", dnp=True,
    note="Second 128 KB for a firmware image over 128 KB: AN76405 Table 17 device 2 (A2/A1/A0 = Vcc/0/1)")
cap("fx3", "100n", "+3V3")
res("fx3", "2k", "I2C_SCL", "+3V3")
res("fx3", "2k", "I2C_SDA", "+3V3")
heading("fx3", "USB reference resistors (AN70707): R_USB2 6.04k 1%, R_USB3 200R 1%.")
res("fx3", "6.04k 1%", "FX3_RUSB2", "GND")
res("fx3", "200 1%", "FX3_RUSB3", "GND")
heading("fx3", "Debug: JTAG (no external pulls; FX3 has internal ones), UART on GPIO55/56.")
put("fx3", stk("Connector", "Conn_ARM_JTAG_SWD_10"), "J", "JTAG", {
    1: "+3V3", 2: "FX3_TMS", 3: "GND", 4: "FX3_TCK", 5: "GND", 6: "FX3_TDO", 7: None, 8: "FX3_TDI",
    9: "GND", 10: "FX3_RESETn"}, "JTAG")
put("fx3", stk("Connector_Generic", "Conn_01x03"), "J", "UART", {1: "FX3_UART_TX", 2: "FX3_UART_RX", 3: "GND"}, "HDR3")
heading("fx3", "Status LED: common-anode RGB on +3V3, cathodes sunk by GPIO50/51/52 (the unused I2S "
        "balls). Pin order per the XL-1615RGBC-RF datasheet: 1 R, 2 common anode, 3 G, 4 B. "
        "States in docs/design.md.")
put("fx3", stk("Device", "LED_RAGB"), "D", "XL-1615RGBC-RF",
    {1: "LED_R_K", 2: "+3V3", 3: "LED_G_K", 4: "LED_B_K"}, "LED1615RGB", lcsc="C965840")
res("fx3", "470", "LED_R_K", "LED_R")
res("fx3", "100", "LED_G_K", "LED_G")
res("fx3", "100", "LED_B_K", "LED_B")
heading("fx3", "Decoupling per AN70707 Table 3. AVDD, U3TXVDDQ, U3RXVDDQ and CVDDQ each behind a "
        "ferrite (AN70707 Figure 1, Appendix B); 22 uF on each USB 3 supply (datasheet).")
for _ in range(8):
    cap("fx3", "100n", "+1V2")
for _ in range(4):
    cap("fx3", "10n", "+1V2")
cap("fx3", "22u", "+1V2")
bead("fx3", "+1V2", "FX3_AVDD")
cap("fx3", "2.2u", "FX3_AVDD")
cap("fx3", "100n", "FX3_AVDD")
for rail in ("FX3_U3TX", "FX3_U3RX"):
    bead("fx3", "+1V2", rail)
    cap("fx3", "22u", rail)
    cap("fx3", "100n", rail)
bead("fx3", "+3V3", "FX3_CVDDQ")
cap("fx3", "100n", "FX3_CVDDQ")
cap("fx3", "10n", "FX3_CVDDQ")
for _ in range(6):
    cap("fx3", "100n", "+3V3")
for _ in range(5):
    cap("fx3", "10n", "+3V3")
cap("fx3", "1u", "VBUS")
cap("fx3", "100n", "VBUS")

# ================================================================ USB sheet
def usb_micro_b():
    """USB 3.0 Micro-B receptacle, Hirose ZX360D-B-10P.

    PROVISIONAL: the connector choice is still open (docs/design.md). Micro-B is the default
    because the FX3's single SuperSpeed lane needs no orientation mux behind it. A USB-C
    variant replaces this function only: the FX3 side of every net (USB3_DP/DM, USB3_RXP/N,
    USB3_TXP_C/TXN_C, VBUS, GND) stays the same.
    """
    heading("usb", "USB 3.0 Micro-B, Hirose ZX360D-B-10P. PROVISIONAL: connector choice open "
            "(docs/design.md); swap usb_micro_b() in tools/gen_sch.py. SS TX AC-coupled with 100 nF, "
            "ESD on the receptacle side of the caps. Pairs wired P to P; AN70707 p.22 allows a "
            "P/N swap on SS RX if the layout wants it. ID open (device). Shell to GND through "
            "100k || 2.2 nF (AN70707 Figure 35). VBUS only reaches the FX3's VBUS detect.")
    put("usb", stk("Connector", "USB3_B_Micro"), "J", "ZX360D-B-10P", {
        1: "VBUS", 2: "USB3_DM", 3: "USB3_DP", 4: None, 5: "GND", 6: "USB3_TXN", 7: "USB3_TXP",
        8: "GND", 9: "USB3_RXN", 10: "USB3_RXP", "SH": "USB3_SHIELD"}, "USBMB3", lcsc="C598201",
        ref="J2", note="Provisional connector choice, see docs/design.md")
    cap("usb", "100n", "USB3_TXN_C", "USB3_TXN")
    cap("usb", "100n", "USB3_TXP_C", "USB3_TXP")
    put("usb", stk("Power_Protection", "TPD4E05U06DQA"), "D", "TPD4E05U06DQAR",
        {1: "USB3_TXN", 2: "USB3_TXP", 4: "USB3_RXP", 5: "USB3_RXN", 3: "GND", 8: "GND",
         10: "USB3_TXN", 9: "USB3_TXP", 7: "USB3_RXP", 6: "USB3_RXN"}, "USON10", lcsc="C138714",
        note="Flow-through: each channel's NC pad opposite (10/9/7/6) carries the same net, so the trace runs straight under the part")
    put("usb", stk("Power_Protection", "USBLC6-2SC6"), "D", "USBLC6-2SC6",
        {1: "USB3_DP", 6: "USB3_DP", 3: "USB3_DM", 4: "USB3_DM", 2: "GND", 5: "VBUS"}, "SOT23-6", lcsc="C7519")
    res("usb", "100k", "USB3_SHIELD", "GND")
    cap("usb", "2.2n", "USB3_SHIELD")
    cap("usb", "10u", "VBUS")


usb_micro_b()

# ================================================================ power sheet
heading("power", "Supply: the PIO 3.3 V rail (pins 17/51, 3.3 V nominal, up to 3.5 V) feeds every FX3 "
        "I/O domain directly (VIO1-5 and CVDDQ, 1.7-3.6 V operating). TLV62569 buck makes the 1.2 V core "
        "and USB 3 supplies from it (SLVSDG0: VFB 0.6 V, R1 = R2 = 100k, 6.8 pF feed-forward for "
        "R2 = 100k, 2.2 uH, 4.7 uF in minimum, 10-47 uF out). EN tied high: the core runs whenever the "
        "console is on.")
put("power", stk("Regulator_Switching", "TLV62569DBV"), "U", "TLV62569DBVR",
    {1: "+3V3", 2: "GND", 3: "SW_1V2", 4: "+3V3", 5: "FB_1V2"}, "SOT23-5", lcsc="C141836")
cap("power", "10u", "+3V3")
cap("power", "100n", "+3V3")
put("power", stk("Device", "L"), "L", "2.2u", {1: "SW_1V2", 2: "+1V2"}, "L4030")
cap("power", "22u", "+1V2")
cap("power", "22u", "+1V2")
res("power", "100k", "+1V2", "FB_1V2")
cap("power", "6.8p", "+1V2", "FB_1V2")
res("power", "100k", "FB_1V2", "GND")
heading("power", "Power LED.")
put("power", stk("Device", "LED"), "D", "GREEN", {1: "PWR_LED_K", 2: "+3V3"}, "LED0603", lcsc="C2986059")
res("power", "1k", "PWR_LED_K", "GND")

# ================================================================ power flags, write
def overflow():
    out = []
    for s in SHEETS.values():
        pw, ph = PAPER[s.paper]
        body = "\n".join(s.items)
        xs = [float(m[1]) for m in re.finditer(r"\(at ([-\d.]+) [-\d.]+", body)]
        ys = [float(m[1]) for m in re.finditer(r"\(at [-\d.]+ ([-\d.]+)", body)]
        if xs and (max(xs) > pw - 12 or max(ys) > ph - 45):  # 45 mm keeps clear of the title block
            out.append(f"{s.name}: content to x={max(xs):.0f}, y={max(ys):.0f} on {s.paper}")
    return out


nets_pins = {}
for ref, sym, unit, nets, value in ALL:
    for k, v in nets.items():
        if v is None:
            continue
        for p in sym.pins[str(k)]:
            if p[3] in (unit, 0):
                nets_pins.setdefault(v, []).append(p[4])
flagged = [n for n, types in nets_pins.items() if "power_in" in types and "power_out" not in types]
heading("power", "Power flags (ERC): " + ", ".join(sorted(flagged)))
for n in sorted(flagged):
    put("power", stk("power", "PWR_FLAG"), "#FLG", "PWR_FLAG", {1: n})

root = L.Sheet("root", "ps1-fx3-cart.kicad_sch", "ps1-fx3-cart: PS1 PIO to USB 3")
root.uuid = ROOT_UUID
root.text("ps1-fx3-cart. A PS1 expansion-port (PIO) cartridge: an FX3 bridges the PIO bus to USB 3 "
          "through GPIF II,\nholds the console in reset until its firmware runs, and can carry an optional "
          "BIOS NOR flash. Design notes: docs/design.md.", 20, 30, 2.0)
sheet_nodes, pages = [], []
for i, s in enumerate(SHEETS.values()):
    x, y = 25 + (i % 3) * 75, 60 + (i // 3) * 45
    sheet_nodes.append(
        f'(sheet (at {x} {y}) (size 60 30) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)'
        f' (fields_autoplaced yes) (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0))'
        f' (uuid "{s.uuid}")'
        f' (property "Sheetname" "{s.name}" (at {x} {y - 0.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))'
        f' (property "Sheetfile" "{s.fname}" (at {x} {y + 30.6} 0) (effects (font (size 1.27 1.27)) (justify left top)))'
        f' (instances (project "{L.PROJECT}" (path "/{ROOT_UUID}" (page "{i + 2}")))))')
    pages.append(f'(path "/{s.uuid}" (page "{i + 2}"))')
    (ROOT / s.fname).write_text(s.render(L.uid()) + ")\n")
(ROOT / root.fname).write_text(
    root.render(ROOT_UUID) + "\n".join(sheet_nodes) +
    f'\n(sheet_instances (path "/" (page "1")) {" ".join(pages)})\n(embedded_fonts no)\n)\n')
ov = overflow()
if ov:
    raise SystemExit("schematic content runs off the page: " + "; ".join(ov))
print("parts:", len({a[0] for a in ALL}), "nets:", len(nets_pins), "flags:", len(flagged))
