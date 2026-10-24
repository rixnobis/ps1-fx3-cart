#!/usr/bin/env python3
"""Check the exported netlist against the intent, independently of gen_sch.py's tables.

ERC passes anything whose pins are all passive and connected by labels, so it cannot see a
mis-wired bus. This reads the KiCad XML netlist and checks:
  1. no net has a single node (a mistyped label makes one);
  2. each PIO connector pin reaches the intended FX3 ball (direct, or through one series 1k
     for the two sense lines);
  3. the reset hold: 2N7002 drain on /RESET, source on GND, gate on GPIO33 with a pull-up;
  4. the default resistors on SBEN, /IRQ10, /IRQ2, DREQ5;
  5. the optional flash: byte-mode address shift, data, strobes, BYTE# low;
  6. every supply ball/pin of the FX3, the flash and the PIO connector sits on its rail.
Parts are found by value, so reference renumbering does not matter.
Usage: check_netlist.py netlist.xml   (exit 1 on any finding)
"""
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PINS = Path(__file__).resolve().parent / "pins"
root = ET.parse(sys.argv[1]).getroot()
val = {c.get("ref"): c.findtext("value") for c in root.find("components")}
node_net, nets = {}, {}
for n in root.find("nets"):
    name = n.get("name")
    nodes = [(x.get("ref"), x.get("pin")) for x in n.findall("node")]
    nets[name] = nodes
    for nd in nodes:
        node_net[nd] = name
bad = []


def one(prefix):
    refs = [r for r, v in val.items() if v.startswith(prefix)]
    if len(refs) != 1:
        raise SystemExit(f"want one part with value {prefix}*, found {refs}")
    return refs[0]


FX3, FLASH, PIO, QR = one("CYUSB3014"), one("S29AL016J"), one("PIO"), one("2N7002")
fx3 = {r["name"]: r["ball"] for r in csv.DictReader(open(PINS / "fx3.csv"))}
ball = lambda g: (FX3, fx3[f"GPIO[{g}]"])  # noqa: E731
conn = lambda p: (PIO, str(p))  # noqa: E731

for name, nodes in nets.items():
    if len(nodes) < 2 and not name.startswith("unconnected-"):
        bad.append(f"single-node net {name}: {nodes}")


def through_r(a, value):
    """Net on the far side of the single resistor of this value on a's net, else None."""
    src = node_net.get(a)
    rs = [r for r, _ in nets.get(src, []) if r.startswith("R") and val[r] == value]
    if len(rs) != 1:
        return None
    far = [n for (r, _), n in node_net.items() if r == rs[0] and n != src]
    return far[0] if far else None


# 2. PIO pin -> FX3 GPIO, from the psx-spx pinout and the docs/design.md pin map.
D_PINS = (6, 40, 7, 41, 8, 42, 9, 43, 10, 44, 11, 45, 12, 46, 13, 47)
A_PINS = (14, 48, 15, 49, 20, 54, 21, 55, 22, 56, 23, 57, 24, 58, 25, 59, 26, 60, 27, 61, 28)
direct = {p: g for g, p in enumerate(D_PINS)}
direct.update({32: 16, 4: 17, 30: 18, 64: 19, 38: 20, 14: 21, 48: 22, 36: 23, 3: 24, 65: 25,
               33: 26, 66: 27, 67: 28, 15: 29, 37: 35, 31: 36, 5: 37, 49: 38})
for p, g in direct.items():
    net = node_net.get(conn(p))
    if net is None or ball(g) not in nets[net]:
        bad.append(f"PIO pin {p} on {net}, want FX3 GPIO[{g}] ({fx3[f'GPIO[{g}]']}) on it")
for p, g in ((2, 34), (39, 39)):
    far = through_r(conn(p), "1k")
    if far is None or ball(g) not in nets.get(far, []):
        bad.append(f"PIO pin {p}: want one 1k to FX3 GPIO[{g}], far side is {far}")

# 3. reset hold
if node_net.get((QR, "3")) != node_net.get(conn(2)):
    bad.append(f"{QR} drain not on PIO /RESET")
if node_net.get((QR, "2")) != "GND":
    bad.append(f"{QR} source on {node_net.get((QR, '2'))}, want GND")
gate = node_net.get((QR, "1"))
if ball(33) not in nets.get(gate, []):
    bad.append(f"{QR} gate net {gate} does not reach GPIO[33]")
if through_r((QR, "1"), "1k") != "+3V3":
    bad.append(f"{QR} gate: want one 1k pull-up to +3V3")

# 4. defaults
for p, rail, what in ((5, "GND", "SBEN"), (37, "+3V3", "/IRQ10"), (31, "+3V3", "/IRQ2"),
                      (3, "GND", "DREQ5")):
    if through_r(conn(p), "10k") != rail:
        bad.append(f"{what} (pin {p}): want one 10k to {rail}")

# 5. flash, S29AL016J TS048 pin numbers. PIO A0 -> A-1 (pin 45), PIO A(k) -> flash A(k-1).
FA = {0: 25, 1: 24, 2: 23, 3: 22, 4: 21, 5: 20, 6: 19, 7: 18, 8: 8, 9: 7, 10: 6, 11: 5, 12: 4,
      13: 3, 14: 2, 15: 1, 16: 48, 17: 17, 18: 16, 19: 9}
want = {45: conn(A_PINS[0])}
want.update({FA[k - 1]: conn(A_PINS[k]) for k in range(1, 21)})
want.update(dict(zip((29, 31, 33, 35, 38, 40, 42, 44), (conn(p) for p in D_PINS[:8]))))
want.update({26: conn(39), 28: conn(30), 11: conn(64), 12: conn(2)})
for fp, cp in want.items():
    a, b = node_net.get((FLASH, str(fp))), node_net.get(cp)
    if a is None or a != b:
        bad.append(f"flash pin {fp} on {a}, want the net of PIO pin {cp[1]} ({b})")
for fp, net in ((47, "GND"), (37, "+3V3"), (27, "GND"), (46, "GND"), (14, "+3V3")):
    if node_net.get((FLASH, str(fp))) != net:
        bad.append(f"flash pin {fp} on {node_net.get((FLASH, str(fp)))}, want {net}")

# 6. supplies
rail = [(r"^VDD$", "+1V2"), (r"^AVDD$", "FX3_AVDD"), (r"^U3TXVDDQ$", "FX3_U3TX"),
        (r"^U3RXVDDQ$", "FX3_U3RX"), (r"^CVDDQ$", "FX3_CVDDQ"), (r"^VIO\d$", "+3V3"),
        (r"^(VSS|AVSS|U3VSSQ)$", "GND"), (r"^(VBUS|VBATT)$", "VBUS")]
checked = 0
for pat, net in rail:
    for name, b in fx3.items():
        if re.match(pat, name):
            for bb in [r["ball"] for r in csv.DictReader(open(PINS / "fx3.csv")) if r["name"] == name]:
                checked += 1
                if node_net.get((FX3, bb)) != net:
                    bad.append(f"FX3 {name} ({bb}) on {node_net.get((FX3, bb))}, want {net}")
for p, net in [(p, "GND") for p in (1, 35, 34, 68, 16, 50, 19, 53)] + [(17, "+3V3"), (51, "+3V3")]:
    checked += 1
    if node_net.get(conn(p)) != net:
        bad.append(f"PIO pin {p} on {node_net.get(conn(p))}, want {net}")

print(f"nets {len(nets)}; PIO lines checked {len(direct) + 2}; flash pins checked {len(want) + 5}; "
      f"supply pins checked {checked}; findings {len(bad)}")
for b in bad:
    print("  " + b)
sys.exit(1 if bad else 0)
