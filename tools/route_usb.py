#!/usr/bin/env python3
"""Planes, the FX3 escape rule area and the USB pairs, by hand geometry (after build_pcb.py place).

Adapted from rixnobis/ps1-av-capture tools/route_usb.py. The FX3 (U1) is on B.Cu with row A
facing the shell line; J2, the SS ESD (D2), the USB 2 ESD (D3) and the SS TX caps are on F.Cu.
Seen from the top, the receptacle's pin order is the ball order mirrored, so:
  - SS TX and RX leave their balls on B.Cu, drop through a via column at x=30 and run east on
    F.Cu over the solid In1 GND. RX passes D2 northward and lands on J2 on F.Cu.
  - TX passes its caps, then D2 northward, then hops to B.Cu under RX and comes back up at J2.
    The hop also swaps P and N: at the caps TXN is the north line, at J2 the south one.
  - D+/D- run on B.Cu over an In2 GND island: east from the balls, north into D3 on F.Cu (in
    pin 1/3, out pin 6/4), back down to B.Cu with P and N swapped, and south under the J2 pin
    row to come up beside pins 2/3.
45-degree bends only. SS pairs are matched to 0.05 mm and D+/D- to 0.25 mm by 45-degree bumps on
one straight segment; the report prints every length. 0.25 mm lines at 0.15 mm gap: 90 ohm
on JLC04161H-3313A L1/L2 and L4/L3 (build_pcb.py net classes; neither the README nor the
.kicad_dru states an impedance). Each pair's vias get a GND via beside them.
"""
import math
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / "ps1-fx3-cart.kicad_pcb"
OX, OY = 100.0, 100.0
BW, BH = 86.36, 63.5             # build_pcb.W, H


# KiCad saves footprints and tracks in UUID order and every build mints fresh UUIDs, so the
# board's own iteration order changes from build to build; the stages that pick "the first"
# candidate or route in arrival order iterate these instead.
def footprints(board):
    return sorted(board.GetFootprints(), key=lambda f: (f.GetReference(), f.GetPosition().x, f.GetPosition().y))


def tracks(board):
    def key(t):
        s, e = t.GetStart(), t.GetEnd()
        w = 0 if t.GetClass() == "PCB_VIA" else t.GetWidth()
        return (t.GetClass(), t.GetNetname(), t.GetLayer(), s.x, s.y, e.x, e.y, w)
    return sorted(board.GetTracks(), key=key)


W = 0.25                          # 90 ohm differential, 0.15 mm gap: pair pitch 0.4
F, B = pcbnew.F_Cu, pcbnew.B_Cu

# Each net: list of (layer, polyline). Coordinates in board mm, worked out in the comments.
PATHS = {
    # ---- SS TX before the caps: balls A6/A5 east on B to the via column, F.Cu to C40/C41 ----
    "USB3_TXN_C": [(B, [(29.0, 31.75), (30.0, 31.75)]),
                   (F, [(30.0, 31.75), (65.8, 31.75), (66.5, 31.05), (67.52, 31.05)])],
    "USB3_TXP_C": [(B, [(29.0, 32.55), (30.0, 32.55)]),
                   (F, [(30.0, 32.55), (30.4, 32.15), (66.0, 32.15), (66.3, 32.45), (67.52, 32.45)])],
    # ---- SS TX after the caps: south round C41, north through D2 (lanes x 72.9 / 73.45), the
    # P/N swap on B.Cu under RX, up again beside J2 pins 6/7 ----
    "USB3_TXN": [(F, [(68.48, 31.05), (69.2, 31.05), (69.6, 31.45), (69.6, 32.55), (70.0, 32.95),
                      (72.5, 32.95), (72.9, 32.55), (72.9, 30.35)]),
                 (B, [(72.9, 30.35), (73.35, 29.9), (74.0, 29.9), (74.25, 29.65), (76.1657, 29.65),
                      (76.6557, 29.16), (79.45, 29.16)]),
                 (F, [(79.45, 29.16), (80.8, 29.16)])],
    "USB3_TXP": [(F, [(68.48, 32.45), (68.9, 32.45), (69.8, 33.35), (73.05, 33.35), (73.45, 32.95),
                      (73.45, 29.25)]),
                 (B, [(73.45, 29.25), (76.0, 29.25), (76.49, 28.76), (78.0, 28.76), (78.25, 28.51),
                      (78.75, 28.51)]),
                 (F, [(78.75, 28.51), (80.8, 28.51)])],
    # ---- SS RX: balls A4/A3 east on B, F.Cu under the TX pair, north through D2 (lanes
    # x 74.55 / 75.05), east into J2 pins 10/9 ----
    "USB3_RXP": [(B, [(29.0, 33.35), (30.0, 33.35)]),
                 (F, [(30.0, 33.35), (30.65, 34.0), (74.15, 34.0), (74.55, 33.6), (74.55, 27.544),
                      (75.284, 26.81), (79.0, 26.81), (79.25, 26.56), (80.8, 26.56)])],
    "USB3_RXN": [(B, [(29.0, 34.15), (30.0, 34.15)]),
                 (F, [(30.0, 34.15), (30.25, 34.4), (74.75, 34.4), (75.05, 34.1), (75.05, 27.61),
                      (75.45, 27.21), (80.8, 27.21)])],
    # ---- D+/D-: balls A10/A9 east on B, north at x 71.2/71.6 (DP steps out to 72.0 past the
    # DM via), F.Cu through D3, swap on the way back to B, south under the J2 pin row ----
    "USB3_DM": [(B, [(29.0, 28.55), (70.8, 28.55), (71.2, 28.15), (71.2, 25.6)]),
                (F, [(71.2, 25.6), (71.85, 24.95), (75.137, 24.95), (76.4, 24.95)]),
                (B, [(76.4, 24.95), (80.0657, 24.95), (80.7, 25.5843), (80.7, 34.81), (80.3, 35.21),
                     (79.2, 35.21)]),
                (F, [(79.2, 35.21), (80.8, 35.21)])],
    "USB3_DP": [(B, [(29.0, 29.35), (29.4, 28.95), (70.9657, 28.95), (71.6, 28.3157), (71.6, 26.6),
                     (72.0, 26.2), (72.0, 22.55)]),
                (F, [(72.0, 22.55), (72.5, 23.05), (76.7, 23.05), (77.1, 23.45), (77.1, 25.75)]),
                (B, [(77.1, 25.75), (77.5, 25.35), (79.9, 25.35), (80.3, 25.75), (80.3, 33.8),
                     (79.9, 34.2), (79.0, 34.2)]),
                (F, [(79.0, 34.2), (79.36, 34.56), (80.8, 34.56)])],
}
# Supply and ground stubs that sit between the pair lines and nothing else can reach:
# (net, layer, polyline, width)
STUBS = [
    ("GND", F, [(74.0, 31.365), (74.0, 32.135), (74.0, 33.05)], 0.25),     # D2 pins 8+3 to a via
    ("GND", F, [(72.863, 24.0), (71.15, 24.0)], 0.25),                     # D3 pin 2
    ("VBUS", F, [(75.137, 24.0), (76.35, 24.0)], 0.3),                     # D3 pin 5
    ("GND", F, [(80.8, 27.86), (79.1, 27.86)], 0.25),                      # J2 pin 8
    ("GND", F, [(80.8, 33.26), (79.2, 33.26)], 0.25),                      # J2 pin 5
]
# Where the polyline meets a capacitor it stops at one pad and the next net starts at the other:
# the 0.96 mm across each SS TX cap counts towards the pair's length.
CAP = {"USB3_TXN": 0.96, "USB3_TXP": 0.96}
VIAS = [  # (net, x, y)  0.45/0.2
    ("USB3_TXN_C", 30.0, 31.75), ("USB3_TXP_C", 30.0, 32.55),
    ("USB3_RXP", 30.0, 33.35), ("USB3_RXN", 30.0, 34.15),
    ("USB3_TXN", 72.9, 30.35), ("USB3_TXP", 73.45, 29.25),
    ("USB3_TXN", 79.45, 29.16), ("USB3_TXP", 78.75, 28.51),
    ("USB3_DM", 71.2, 25.6), ("USB3_DP", 72.0, 22.55),
    ("USB3_DM", 76.4, 24.95), ("USB3_DP", 77.1, 25.75),
    ("USB3_DM", 79.2, 35.21), ("USB3_DP", 79.0, 34.2),
    # ground returns beside each signal via pair, and the ESD/receptacle ground pins
    ("GND", 30.0, 30.95), ("GND", 30.0, 34.95), ("GND", 72.1, 30.35), ("GND", 79.45, 30.0),
    ("GND", 77.8, 24.3), ("GND", 74.0, 33.05), ("GND", 71.15, 24.0), ("GND", 79.1, 27.86),
    ("GND", 79.2, 33.26),
    ("VBUS", 76.35, 24.0),
]
# L2 is solid GND. L3 carries +3V3 everywhere, a +1V2 island under the FX3 that runs south to the
# buck (L1, C46/C47) and the ferrites, and GND under the B.Cu D+/D- run and the TX hop so those
# lines have a ground reference too.
BOARD = ((0.3, 0.3), (BW - 0.3, 0.3), (BW - 0.3, BH - 0.3), (0.3, BH - 0.3))
# The ball field is x 21.0-29.0, y 27.75-35.75. The island edge passes between the edge balls
# and their outward dogbone vias (0.4 out), so +3V3 edge balls reach +3V3 and +1V2 edge balls
# fan inward onto the island.
V12_ISLAND = ((21.03, 27.78), (29.3, 27.78), (29.3, 35.72), (36.0, 35.72), (36.0, 48.8),
              (26.8, 48.8), (26.8, 35.72), (21.03, 35.72))
# It also takes the SS via column at x=30, so the return vias there tie In1 to In2.
GND_ISLAND = ((29.45, 27.6), (69.6, 27.6), (69.6, 21.6), (BW - 0.3, 21.6), (BW - 0.3, 36.9),
              (69.6, 36.9), (69.6, 30.0), (31.0, 30.0), (31.0, 35.6), (29.45, 35.6))
PLANES = [
    (pcbnew.In1_Cu, "GND", 0, BOARD),
    (pcbnew.In2_Cu, "+3V3", 0, BOARD),
    (pcbnew.In2_Cu, "+1V2", 1, V12_ISLAND),
    (pcbnew.In2_Cu, "GND", 2, GND_ISLAND),
]
# Rule area the .kicad_dru keys its 0.1 mm escape clearance on: the ball field plus 1.2 mm.
ESC_BOX = (19.8, 26.55, 30.2, 36.95)
# Pairs to match: (N nets, P nets, tolerance)
PAIRS = [(("USB3_TXN_C", "USB3_TXN"), ("USB3_TXP_C", "USB3_TXP"), 0.05),
         (("USB3_RXN",), ("USB3_RXP",), 0.05),
         (("USB3_DM",), ("USB3_DP",), 0.25)]
# net -> [(path index, segment index, side +1 right/-1 left of travel, max bump height, share)]
# The long straight F.Cu (SS) or B.Cu (D+/D-) runs away from the other pair.
BUMP_AT = {"USB3_TXN_C": [(1, 0, -1, 0.5, 1.0)], "USB3_TXP_C": [(1, 1, +1, 0.5, 1.0)],
           "USB3_RXP": [(1, 1, -1, 0.5, 1.0)], "USB3_RXN": [(1, 1, +1, 0.5, 1.0)],
           "USB3_DM": [(0, 0, -1, 0.5, 1.0)], "USB3_DP": [(0, 1, +1, 0.5, 1.0)]}


def seglen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def netlen(net):
    return sum(seglen(p) for _, p in PATHS.get(net, [])) + CAP.get(net, 0.0)


def bump(pts, i, side, extra, teeth=1, hmax=None):
    """Replace straight segment i with `teeth` 45-degree bumps bulging sideways by h. Each
    tooth (up h, flat 0.3, down h) adds 2h(sqrt2 - 1) mm."""
    a, b = pts[i], pts[i + 1]
    L = math.dist(a, b)
    k = 2 * (math.sqrt(2) - 1)
    if hmax:
        teeth = max(teeth, math.ceil(extra / (k * hmax)))
    h = extra / (k * teeth)
    gap = 0.5                                      # between teeth: 2W
    pitch = 2 * h + 0.3 + gap
    span = teeth * pitch - gap
    assert span < L - 0.2, ("segment too short for the bump", a, b, h, teeth)
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = -uy * side, ux * side
    out = []
    t = (L - span) / 2
    assert t >= 0.3, ("bump would leave a stub shorter than 0.3 mm", a, b, t)
    for _ in range(teeth):
        p1 = (a[0] + ux * t, a[1] + uy * t)
        p2 = (p1[0] + ux * h + nx * h, p1[1] + uy * h + ny * h)
        p3 = (p2[0] + ux * 0.3, p2[1] + uy * 0.3)
        p4 = (p3[0] + ux * h - nx * h, p3[1] + uy * h - ny * h)
        out += [p1, p2, p3, p4]
        t += pitch
    return pts[:i + 1] + out + pts[i + 1:]


def match():
    for n_nets, p_nets, tol in PAIRS:
        ln = sum(netlen(n) for n in n_nets)
        lp = sum(netlen(n) for n in p_nets)
        if abs(ln - lp) <= tol:
            continue
        short = p_nets if lp < ln else n_nets
        site = next(n for n in short if n in BUMP_AT)
        extra = abs(ln - lp)
        for pi, si, side, hmax, share in BUMP_AT[site]:
            layer, pts = PATHS[site][pi]
            PATHS[site][pi] = (layer, bump(pts, si, side, extra * share, hmax=hmax))


def v2(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def add_track(board, nets, net, layer, a, b, w):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(v2(*a))
    t.SetEnd(v2(*b))
    t.SetWidth(pcbnew.FromMM(w))
    t.SetLayer(layer)
    t.SetNet(nets[net])
    t.SetLocked(True)           # hand geometry: later stages route around it
    board.Add(t)


def zone(board, nets, layer, net, prio, poly):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(nets[net])
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(pcbnew.FromMM(0.2))
    z.SetMinThickness(pcbnew.FromMM(0.2))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in poly:
        ol.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
    board.Add(z)


def esc_area(board):
    area = pcbnew.ZONE(board)
    area.SetIsRuleArea(True)
    area.SetZoneName("BGA_ESC")
    area.SetDoNotAllowTracks(False)
    area.SetDoNotAllowVias(False)
    area.SetDoNotAllowPads(False)
    area.SetDoNotAllowFootprints(False)
    area.SetDoNotAllowZoneFills(False)
    ls = pcbnew.LSET()
    for L in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(L)
    area.SetLayerSet(ls)
    ol = area.Outline()
    ol.NewOutline()
    x0, y0, x1, y1 = ESC_BOX
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ol.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
    board.Add(area)


def check_pads(board):
    """Every polyline end that names a pad must sit on that pad of the right net."""
    pads = {}
    for fp in footprints(board):
        for p in fp.Pads():
            pads.setdefault(p.GetNetname(), []).append(p)
    ends = [(net, pts[0]) for net, paths in PATHS.items() for _, pts in paths]
    ends += [(net, pts[-1]) for net, paths in PATHS.items() for _, pts in paths]
    ends += [(net, pts[0]) for net, _, pts, _ in STUBS]
    vias = {(n, x, y) for n, x, y in VIAS}
    for net, (x, y) in ends:
        if (net, x, y) in vias:
            continue
        hit = [p for p in pads.get(net, []) if p.HitTest(v2(x, y))]
        assert hit, ("polyline end on no pad of its net", net, x, y)


def main():
    match()
    board = pcbnew.LoadBoard(str(PCB))
    nets = board.GetNetsByName()
    # Runs on the fresh board build_pcb.py place writes. pcbnew 10.0.7 crashes on later API
    # calls after board.Remove(), so this script never removes anything: re-run place first.
    assert len(board.GetTracks()) == 0, "run build_pcb.py place first"
    assert [z.GetZoneName() for z in board.Zones()] == ["PIO_BODY"], "run build_pcb.py place first"
    check_pads(board)
    for net, paths in PATHS.items():
        for layer, pts in paths:
            for a, b in zip(pts, pts[1:]):
                add_track(board, nets, net, layer, a, b, W)
    for net, layer, pts, w in STUBS:
        for a, b in zip(pts, pts[1:]):
            add_track(board, nets, net, layer, a, b, w)
    for net, x, y in VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(v2(x, y))
        v.SetWidth(pcbnew.FromMM(0.45))
        v.SetDrill(pcbnew.FromMM(0.2))
        v.SetNet(nets[net])
        v.SetLocked(True)
        board.Add(v)
    for layer, net, prio, poly in PLANES:
        zone(board, nets, layer, net, prio, poly)
    esc_area(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    for n_nets, p_nets, tol in PAIRS:
        ln = sum(netlen(n) for n in n_nets)
        lp = sum(netlen(n) for n in p_nets)
        print(f"{'+'.join(n_nets):22s} {ln:7.3f}  {'+'.join(p_nets):22s} {lp:7.3f}  "
              f"skew {abs(ln - lp):.3f} (limit {tol})")
        assert abs(ln - lp) <= tol + 1e-6


if __name__ == "__main__":
    main()
