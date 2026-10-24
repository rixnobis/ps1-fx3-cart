#!/usr/bin/env python3
"""Build ps1-fx3-cart.kicad_pcb from the schematic netlist.

  build_pcb.py place   - board, net classes, rules, outline, shell line, part placement

Coordinates are millimetres from the board's top-left corner. The board is the owner's
PIO-Dev-3 outline (86.36 x 63.5): the PIO connector runs down the left edge at x=5.08 and the
silkscreen line at x=38.1 marks the top of the PlayStation shell. B.Cu faces the console, so a
back-side part must sit between the connector body and that line and be flat; everything tall,
the USB receptacle and the debug headers are on F.Cu. ICs and connectors are placed by hand
(FIXED, HAND); every passive goes next to the pin it serves (place_rest), on its host's side.
The board is built from scratch on every run: pcbnew crashes after board.Remove().
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
NAME = "ps1-fx3-cart"
PCB = ROOT / f"{NAME}.kicad_pcb"
PRO = ROOT / f"{NAME}.kicad_pro"
SCH = ROOT / f"{NAME}.kicad_sch"
LIBS = {"fx3-cart": ROOT / "lib" / "cart.pretty"}
FPDIR = Path("/usr/share/kicad/footprints")

OX, OY = 100.0, 100.0           # sheet offset of the board origin
W, H = 86.36, 63.5              # PIO-Dev-3 outline
SHELL_X = 38.1                  # top of the PlayStation shell (PIO-Dev-3 tPlace line)
# Back-side parts (outline incl. GAP) live between the connector body and the shell line.
BACK_X0, BACK_X1 = 10.7, SHELL_X - 0.3
F, B = "F", "B"

# PIO connector holes as on PIO-Dev-3 (pcsx-redux hardware/PIO-Dev/PCB/PIO-Dev-3.brd: element
# PIO, package pixel.lbr PIOCONN, x=5.08 y=31.75 R270, EAGLE y up), in this board's y-down frame.
# PIO-Dev-3 places the package unmirrored on EAGLE top while its body sits on the bottom (the
# side its flat TQFP100/TSOP48 share with it), so the land pattern is drawn as seen from the
# solder side. KiCad's Flip would mirror the holes and swap pin 1 with pin 34: J1 therefore
# stays an F.Cu footprint at 270 deg, which reproduces PIO-Dev-3's holes, and its body on B is
# marked by J1_BODY (B.SilkS outline and a B.Cu no-footprint rule area).
PIO_HOLES = {"1": (6.033, 52.705), "2": (7.943, 51.435), "34": (7.943, 10.795),
             "35": (2.213, 52.705), "68": (4.123, 10.795)}
J1_BODY = (0.2, 0.0, 5.08 + 5.05, H)    # PIOCONN tPlace outline (x 0.03-10.13), silk kept off the edge

# Hand placement: ref -> (x, y, angle, side). Angles are asserted in check_orientation().
FIXED = {
    "J1": (5.08, 31.75, 270, F),   # see PIO_HOLES
    "U1": (25.0, 31.75, 90, B),   # FX3 on the back: row A (USB) faces the shell line, row L (GPIF) faces J1
    "J2": (W - 4.22, 31.75, 90, F),  # Micro-B 3.0: mating face (+4.22 local) flush with the right edge
}
HAND = {
    "Y1": (33.5, 26.0, 90, B),      # 19.2 MHz: XI/XO (C6/C7) sit between the USB balls, so just north of their via field
    "U2": (23.0, 11.0, 0, F),      # NOR flash (DNP), front, pin 1 row facing J1
    "U5": (20.0, 44.0, 0, F),      # 1V2 buck, front, under the FX3's south-west quarter
    "L1": (26.0, 44.0, 0, F),
    "Q1": (14.0, 54.0, 0, F),      # /RESET hold, near J1 pin 2
    # USB corridor on F.Cu from the FX3's row A (vias at x~31) to J2
    "D2": (74.0, 31.75, 90, F),    # SS ESD, flow-through
    "C40": (68.0, 31.05, 0, F), "C41": (68.0, 32.45, 0, F),   # SS TX AC caps
    "D3": (74.0, 24.0, 0, F),      # USB 2 ESD
    # debug and boot along the top edge, past the shell line
    "J3": (46.0, 5.0, 0, F),       # JTAG 2x5 1.27 SMD
    "J4": (53.5, 3.5, 90, F),      # UART 1x3 2.54
    "JP1": (62.5, 3.5, 90, F),     # USB boot jumper
    "SW1": (73.0, 5.0, 0, F),      # reset
    "D1": (81.5, 4.0, 0, F),       # status RGB
    "D4": (81.5, 9.0, 0, F),       # power LED
    "U3": (48.0, 16.0, 0, F), "U4": (48.0, 23.0, 0, F),       # boot EEPROM + DNP spare
}
# Areas no passive is auto-placed in: (x0, y0, x1, y1, side)
KEEPOUT = [
    (BACK_X0, 0.0, 18.5, H, B),             # back GPIF channel between J1 and the FX3
    (31.0, 28.5, BACK_X1, 35.5, B),         # USB balls (row A) to their vias, back
    (29.0, 29.0, W, 34.5, F),               # USB corridor on the front
    (W - 11.0, 22.5, W, 41.0, F),           # room for a USB-C receptacle in J2's place
    (SHELL_X - 0.3, 0.0, SHELL_X + 0.3, H, F), (SHELL_X - 0.3, 0.0, SHELL_X + 0.3, H, B),
]
PREFER = {"C2": "Y1", "C3": "Y1"}   # ref -> host: crystal load caps at the crystal
# A cap from a multi-pin rail to GND decouples its sheet's main part, not a header or an EEPROM
DECAP_HOSTS = {"/FX3/": ("U1",), "/Power/": ("U5", "L1"), "/Flash/": ("U2",), "/USB/": ("J2",)}
ANCHOR_SKIP = {"GND"}
EDGE = 1.0                      # keep parts this far inside the outline
GAP = 0.5                       # clearance between part outlines
RING = {"U1": 0.9}              # escape ring around the BGA
DIFF_NETS = ["USB3_TXP*", "USB3_TXN*", "USB3_RXP", "USB3_RXN", "USB3_DP", "USB3_DM"]
POWER_NETS = ["VBUS", "FX3_AVDD", "FX3_U3*", "FX3_CVDDQ", "SW_*"]


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def netlist():
    xml = ROOT / "build" / "netlist.xml"
    xml.parent.mkdir(exist_ok=True)
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
                    "-o", str(xml), str(SCH)], check=True, capture_output=True)
    r = ET.parse(xml).getroot()
    comps = {}
    for c in r.find("components"):
        fields = {f.get("name"): f.text for f in c.iter("field")}
        dnp = any(p.get("name") == "dnp" for p in c.findall("property"))
        comps[c.get("ref")] = {"value": c.findtext("value"), "footprint": c.findtext("footprint"),
                               "uuid": c.findtext("tstamps"), "fields": fields, "dnp": dnp,
                               "sheet": c.find("sheetpath").get("names")}
    pads = {}
    for n in r.find("nets"):
        for node in n:
            pads[(node.get("ref"), node.get("pin"))] = n.get("name")
    return comps, pads


def write_project():
    """Net classes and JLC 4-layer rules, as ps1-av-capture (docs/stackup.md there)."""
    d = json.loads(PRO.read_text())
    board = d.setdefault("board", {})
    ds = board.setdefault("design_settings", {})
    ns = d.setdefault("net_settings", {})
    base = {"bus_width": 12, "clearance": 0.15, "diff_pair_gap": 0.15, "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.25, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
            "tuning_profile": "", "via_diameter": 0.45, "via_drill": 0.2, "wire_width": 6}
    ns["classes"] = [dict(base, name="Default", priority=2147483647, track_width=0.2),
                     dict(base, name="Power", priority=1, track_width=0.5),
                     dict(base, name="Plane", priority=0, track_width=0.25),
                     # 90 ohm on JLC04161H-3313A L1/L2
                     dict(base, name="USB", priority=0, track_width=0.25, clearance=0.15)]
    ns["netclass_patterns"] = ([{"netclass": "USB", "pattern": n} for n in DIFF_NETS] +
                               [{"netclass": "Power", "pattern": n} for n in POWER_NETS] +
                               [{"netclass": "Plane", "pattern": n} for n in ("GND", "+3V3", "+1V2")])
    ns["netclass_assignments"] = {}
    rules = ds.setdefault("rules", {})
    # 0.1/0.1 floor for the FX3 escape box only; ps1-fx3-cart.kicad_dru holds the rest to 0.127/0.15
    rules.update({"min_clearance": 0.1, "min_track_width": 0.1, "min_via_diameter": 0.45,
                  "min_via_annular_width": 0.1, "min_through_hole_diameter": 0.2,
                  "min_copper_edge_clearance": 0.4, "min_hole_clearance": 0.2,
                  "min_hole_to_hole": 0.4, "min_silk_clearance": 0.0, "min_text_height": 0.8,
                  "min_text_thickness": 0.15})
    PRO.write_text(json.dumps(d, indent=2) + "\n")


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = LIBS.get(lib, FPDIR / f"{lib}.pretty")
    fp = pcbnew.FootprintLoad(str(path), name)
    assert fp is not None, fpid
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def seg(board, a, b, layer, width):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pt(*a))
    s.SetEnd(pt(*b))
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    board.Add(s)


def outline(board):
    for a, b in [((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))]:
        seg(board, a, b, pcbnew.Edge_Cuts, 0.1)


def shell_line(board):
    """The top of the console shell, on both silkscreens, with a small label."""
    for layer, dx, mirror in ((pcbnew.F_SilkS, 0.9, False), (pcbnew.B_SilkS, -0.9, True)):
        seg(board, (SHELL_X, 0.3), (SHELL_X, H - 0.3), layer, 0.3)
        t = pcbnew.PCB_TEXT(board)
        t.SetText("shell")
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        t.SetTextThickness(mm(0.15))
        t.SetTextAngleDegrees(90)
        t.SetMirrored(mirror)
        t.SetPosition(pt(SHELL_X + dx, H - 4.0))
        board.Add(t)


def j1_body(board):
    """J1's body is on the back (see PIO_HOLES): outline it on B.SilkS and keep B footprints off it."""
    x0, y0, x1, y1 = J1_BODY
    for a, b in [((x0, y0 + 0.3), (x0, y1 - 0.3)), ((x1, y0 + 0.3), (x1, y1 - 0.3))]:
        seg(board, a, b, pcbnew.B_SilkS, 0.15)
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayer(pcbnew.B_Cu)
    z.SetZoneName("PIO_BODY")
    z.SetDoNotAllowFootprints(True)
    z.SetDoNotAllowTracks(False)
    z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowZoneFills(False)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ol.Append(mm(OX + x), mm(OY + y))
    board.Add(z)


def padxy(board, ref, num):
    fp = board.FindFootprintByReference(ref)
    p = [q for q in fp.Pads() if q.GetNumber() == num][0].GetPosition()
    return round(pcbnew.ToMM(p.x) - OX, 3), round(pcbnew.ToMM(p.y) - OY, 3)


def check_orientation(board):
    """Each hand-placed part must face where the floorplan says. Fails loudly otherwise."""
    for num, want in PIO_HOLES.items():
        got = padxy(board, "J1", num)
        assert max(abs(got[0] - want[0]), abs(got[1] - want[1])) < 0.01, ("J1 pad", num, got, want)
    fx, fy = FIXED["U1"][:2]
    u1 = board.FindFootprintByReference("U1")
    assert u1.IsFlipped(), "U1 not on B.Cu"
    a4, l4, k1 = padxy(board, "U1", "A4"), padxy(board, "U1", "L4"), padxy(board, "U1", "K1")
    assert a4[0] > fx + 3, ("U1 row A (USB) not facing the shell line", a4)
    assert l4[0] < fx - 3, ("U1 row L (GPIF) not facing J1", l4)
    xi = padxy(board, "U1", "C6")
    y1 = padxy(board, "Y1", "1")
    assert ((xi[0] - y1[0]) ** 2 + (xi[1] - y1[1]) ** 2) ** 0.5 < 8, ("Y1 not at XI", xi, y1)
    p1, sh = padxy(board, "J2", "1"), padxy(board, "J2", "SH")
    assert p1[0] < FIXED["J2"][0] and W - 3 < pcbnew.ToMM(
        board.FindFootprintByReference("J2").GetCourtyard(pcbnew.F_CrtYd).BBox().GetRight()) - OX <= W + 0.5, \
        ("J2 mating face not at the right edge", p1)
    u2 = padxy(board, "U2", "1")
    assert u2[0] < HAND["U2"][0] - 5, ("U2 pin 1 row not facing J1", u2)
    print("orientation ok: J1 pad1", padxy(board, "J1", "1"), "| U1 A4", a4, "L4", l4, "K1", k1,
          "| J2 pad1", p1, "| U2 pad1", u2)


def fp_box(fp, margin=0.0):
    """Outline of a footprint from its pads and fab/courtyard graphics, in board mm."""
    xs, ys = [], []
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        xs += [bb.GetLeft(), bb.GetRight()]
        ys += [bb.GetTop(), bb.GetBottom()]
    for g in fp.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd, pcbnew.F_Fab, pcbnew.B_Fab) \
                and g.GetClass() != "PCB_TEXT":
            bb = g.GetBoundingBox()
            xs += [bb.GetLeft(), bb.GetRight()]
            ys += [bb.GetTop(), bb.GetBottom()]
    f = lambda v, o: pcbnew.ToMM(v) - o  # noqa: E731
    return (min(f(x, OX) for x in xs) - margin, min(f(y, OY) for y in ys) - margin,
            max(f(x, OX) for x in xs) + margin, max(f(y, OY) for y in ys) + margin)


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def is_tht(fp):
    return any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in fp.Pads())


def region_ok(bx, side):
    if bx[0] < EDGE or bx[1] < EDGE or bx[2] > W - EDGE or bx[3] > H - EDGE:
        return False
    return side == F or (bx[0] >= BACK_X0 and bx[2] <= BACK_X1)


def set_side(fp, side):
    if (side == B) != fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def place_rest(board, comps, pads, sides):
    """HAND tier, then every other part next to the pad it serves, on its host's side.

    A part's anchor is the pad of an already-placed part on the net it shares with the fewest
    other pads, GND excluded. A decoupling cap (rail + GND) goes to the rail pin of an IC on its
    own sheet with the fewest caps so far. The part is pushed out from its host's outline until
    it clears everything placed on that side (through-hole parts block both sides); a candidate
    anchor with no room is skipped for the next one.
    """
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    placed = set(FIXED)
    for ref, (x, y, a, side) in HAND.items():
        set_side(fps[ref], side)
        fps[ref].SetPosition(pt(x, y))
        fps[ref].SetOrientationDegrees(a)
        sides[ref] = side
        placed.add(ref)
    boxes = {F: {}, B: {}}

    def block(ref, bx):
        tht = is_tht(fps[ref])
        for s in (F, B):
            if s == sides[ref] or tht:
                boxes[s][ref] = bx
    for r in placed:
        block(r, fp_box(fps[r], GAP + RING.get(r, 0.0)))
    keep = {s: [k[:4] for k in KEEPOUT if k[4] == s] for s in (F, B)}
    keep[B].append(J1_BODY)
    fan = {}
    for (r, _), n in pads.items():
        fan[n] = fan.get(n, 0) + 1
    caps_on = {}
    rails = {n for n, k in fan.items() if k >= 6}
    todo = sorted(set(comps) - placed, key=lambda r: (r[0] in "RC", r))
    stuck = 0
    while todo and stuck < len(todo):
        ref = todo.pop(0)
        fp = fps[ref]
        nets = [pads.get((ref, p.GetNumber())) for p in fp.Pads()]
        nets = [n for n in nets if n and n not in ANCHOR_SKIP and not n.startswith("unconnected")]
        decap = ref[0] == "C" and "GND" in [pads.get((ref, p.GetNumber())) for p in fp.Pads()]
        cands = []
        for n in nets:
            for (r2, pin), n2 in pads.items():
                if n2 == n and r2 != ref and r2 in placed:
                    if decap and n in rails and r2 not in DECAP_HOSTS.get(comps[ref]["sheet"], ()):
                        continue
                    cands.append((fan[n], caps_on.get((r2, pin), 0), r2, pin, n))
        if not cands:
            todo.append(ref)
            stuck += 1
            continue
        stuck = 0
        key = (lambda c: (c[1], c[0], c[2], c[3])) if decap else (lambda c: (c[0], c[1], c[2], c[3]))
        pref = [c for c in cands if c[2] == PREFER.get(ref)]
        best = None
        for _, _, r2, pin, net in sorted(pref, key=key) + sorted(cands, key=key):
            best = try_place(board, fps, ref, r2, pin, net, pads, sides, boxes, keep)
            if best:
                break
        if not best:
            for s in (F, B):
                print(s, {r: tuple(round(v, 1) for v in bx) for r, bx in boxes[s].items()})
        assert best, ("no room for", ref, cands)
        caps_on[(r2, pin)] = caps_on.get((r2, pin), 0) + 1
        sides[ref] = sides[r2]
        block(ref, best)
        placed.add(ref)
    assert not todo, ("parts with no placed neighbour", todo)
    print("placed", len(placed) - len(FIXED) - len(HAND), "parts next to their anchors")


def try_place(board, fps, ref, r2, pin, net, pads, sides, boxes, keep):
    fp = fps[ref]
    side = sides[r2]
    set_side(fp, side)
    ax, ay = padxy(board, r2, pin)
    host = boxes[side][r2]
    cx, cy = (host[0] + host[2]) / 2, (host[1] + host[3]) / 2
    dx, dy = ax - cx, ay - cy
    horiz = abs(dx) * (host[3] - host[1]) >= abs(dy) * (host[2] - host[0])
    if r2 == "J1":
        horiz, dx = True, 1.0       # the connector spans the board height: always step right
    ux, uy = ((1 if dx >= 0 else -1), 0) if horiz else (0, (1 if dy >= 0 else -1))
    fp.SetOrientationDegrees(0 if horiz else 90)
    mine = [p for p in fp.Pads() if pads.get((ref, p.GetNumber())) == net]
    if mine and len(list(fp.Pads())) == 2:
        fp.SetPosition(pt(0, 0))     # pad on the anchor net faces the anchor
        px = pcbnew.ToMM(mine[0].GetPosition().x) - OX
        py = pcbnew.ToMM(mine[0].GetPosition().y) - OY
        if (px * ux + py * uy) > 0:
            fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)
    obst = list(boxes[side].values()) + keep[side]
    for step in range(0, 60):
        d = step * 0.5
        for lat in [0] + [s * k * 0.5 for k in range(1, 60) for s in (1, -1)]:
            x = (host[2] if ux > 0 else host[0] if ux < 0 else ax + lat) if horiz else ax + lat
            y = (host[3] if uy > 0 else host[1] if uy < 0 else ay + lat) if not horiz else ay + lat
            fp.SetPosition(pt(x, y))
            bx = fp_box(fp, GAP)
            w2, h2 = (bx[2] - bx[0]) / 2, (bx[3] - bx[1]) / 2
            x += ux * (w2 + d)
            y += uy * (h2 + d)
            fp.SetPosition(pt(x, y))
            bx = fp_box(fp, GAP)
            if not region_ok(bx, side) or any(overlaps(bx, o) for o in obst):
                continue
            return bx
    return None


def place():
    write_project()
    comps, pads = netlist()
    board = pcbnew.NewBoard(str(PCB))
    board.SetCopperLayerCount(4)
    nets = {}
    for name in sorted(set(pads.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    sides = {}
    stage_x, stage_y = W + 10, 0.0          # unplaced passives wait off-board, in a column
    for ref, c in sorted(comps.items()):
        fp = load_fp(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"]))
        if c["fields"].get("LCSC"):
            fp.SetField("LCSC", c["fields"]["LCSC"])
            fp.GetField("LCSC").SetVisible(False)
        if c["dnp"]:
            fp.SetDNP(True)
        board.Add(fp)
        if ref in FIXED:
            x, y, a, side = FIXED[ref]
            sides[ref] = side
            set_side(fp, side)
        else:
            x, y, a = stage_x, stage_y, 0
            stage_y += 3.0
            if stage_y > 150:
                stage_x, stage_y = stage_x + 6, 0.0
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(a)
        for pad in fp.Pads():
            net = pads.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])
    place_rest(board, comps, pads, sides)
    check_orientation(board)
    outline(board)
    shell_line(board)
    j1_body(board)
    back = sorted((fp.GetReference() for fp in board.GetFootprints() if fp.IsFlipped()),
                  key=lambda r: (r[0], int(r[1:]) if r[1:].isdigit() else 0))
    for fp in board.GetFootprints():
        if fp.IsFlipped():
            bx = fp_box(fp)
            assert BACK_X0 <= bx[0] and bx[2] <= SHELL_X, ("back part outside the flat zone", fp.GetReference(), bx)
    board.Save(str(PCB))
    print("back:", len(back), " ".join(back))
    print("fixed", len(FIXED), "hand", len(HAND))


if __name__ == "__main__":
    {"place": place}[sys.argv[1]]()
