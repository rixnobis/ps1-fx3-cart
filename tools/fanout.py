#!/usr/bin/env python3
"""Fan every SMD pad on a plane net out to its plane: a short stub and a 0.45/0.2 via.

Adapted from rixnobis/ps1-av-capture tools/fanout.py. Runs after route_usb.py on the fresh
board. GND has the whole of In1 (and an In2 island under the USB run); +3V3 and +1V2 have In2
regions (route_usb.PLANES), and a pad is only fanned out where its net's plane covers the via.
The FX3's balls (U1, on B.Cu) get a dogbone into a diagonal gap, outward first; other pads get
a via straight out from the part's centre, then sideways if that spot is taken. J1 is
through-hole and meets the planes through its own barrels, so it is never touched. Prints what
it placed and what it could not.
"""
import math
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from route_usb import PLANES, OX, OY, BW, BH, PCB, footprints, tracks  # noqa: E402

VIA_D, VIA_DRILL, CLEAR, STUB = 0.45, 0.2, 0.2, 0.25
BGA = "U1"


def mm(v):
    return pcbnew.ToMM(v)


def inside(poly, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def plane_net_at(layer, x, y):
    """Net the given plane layer carries at (x, y): highest-priority zone covering the point."""
    best = None
    for lay, net, prio, poly in PLANES:
        if lay == layer and inside(list(poly), x, y) and (best is None or prio > best[0]):
            best = (prio, net)
    return best[1] if best else None


def reaches_plane(net, x, y):
    """The via lands inside its net's region with room for the zone clearance on every side."""
    for lay in (pcbnew.In1_Cu, pcbnew.In2_Cu):
        if all(plane_net_at(lay, x + dx, y + dy) == net
               for dx, dy in ((0, 0), (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3))):
            return True
    return False


def rect_dist(px, py, r):
    dx = max(r[0] - px, 0, px - r[2])
    dy = max(r[1] - py, 0, py - r[3])
    return math.hypot(dx, dy)


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    L2 = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L2))
    return math.hypot(px - ax - t * (bx - ax), py - ay - t * (by - ay))


def collinear(s, t, tol=0.01):
    """Two segments on one line sharing more than a point: redundant copper."""
    (ax, ay), (bx, by) = s
    L = math.hypot(bx - ax, by - ay) or 1.0
    if any(abs((bx - ax) * (qy - ay) - (by - ay) * (qx - ax)) / L > tol for qx, qy in t):
        return False
    pts = [q for q in s if seg_dist(*q, *t) < tol] + [q for q in t if seg_dist(*q, *s) < tol]
    return len({(round(x, 4), round(y, 4)) for x, y in pts}) >= 2


def main():
    board = pcbnew.LoadBoard(str(PCB))
    nets = board.GetNetsByName()
    plane_nets = {n for _, n, _, _ in PLANES}
    # (net, kind, geometry, half-width, outer faces it occupies): F.Cu and B.Cu parts overlap in
    # plan on this board, so a stub only clears copper on its own face; a via clears both
    obst = []
    FB = frozenset("FB")

    def faces(item):
        return frozenset(c for c, L in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)) if item.IsOnLayer(L))
    for fp in footprints(board):
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            if p.GetShape(p.GetPrincipalLayer()) == pcbnew.PAD_SHAPE_CIRCLE:   # BGA balls, round holes
                pos = p.GetPosition()
                obst.append((p.GetNetname(), "circle", (mm(pos.x) - OX, mm(pos.y) - OY),
                             mm(bb.GetWidth()) / 2, faces(p)))
                continue
            obst.append((p.GetNetname(), "rect",
                         (mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY,
                          mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY), 0.0, faces(p)))
    n_pad_obst = len(obst)
    for t in tracks(board):
        if t.GetClass() == "PCB_VIA":
            obst.append((t.GetNetname(), "circle", (mm(t.GetPosition().x) - OX,
                         mm(t.GetPosition().y) - OY), mm(t.GetWidth(pcbnew.F_Cu)) / 2, FB))
        else:
            obst.append((t.GetNetname(), "seg", ((mm(t.GetStart().x) - OX, mm(t.GetStart().y) - OY),
                         (mm(t.GetEnd().x) - OX, mm(t.GetEnd().y) - OY)), mm(t.GetWidth()) / 2, faces(t)))
    # drilled holes (vias added below join this): hole-to-hole spacing against every barrel
    holes = [(mm(p.GetPosition().x) - OX, mm(p.GetPosition().y) - OY, mm(p.GetDrillSize().x) / 2)
             for fp in footprints(board) for p in fp.Pads() if p.HasHole()]
    holes += [(mm(t.GetPosition().x) - OX, mm(t.GetPosition().y) - OY, mm(t.GetDrillValue()) / 2)
              for t in tracks(board) if t.GetClass() == "PCB_VIA"]

    def clear(net, x, y, r, face=None):
        """Point (x, y) with radius r keeps CLEAR from every other-net obstacle on the face
        (both faces for a via) and from the edge."""
        if not (0.6 + r < x < BW - 0.6 - r and 0.6 + r < y < BH - 0.6 - r):
            return False
        for n, kind, g, hw, fc in obst:
            if n == net or (face is not None and face not in fc):
                continue
            if kind == "rect":
                d = rect_dist(x, y, g)
            elif kind == "circle":
                d = math.hypot(x - g[0], y - g[1]) - hw
            else:
                d = seg_dist(x, y, *g) - hw
            if d < r + CLEAR:
                return False
        return True

    def stub_clear(net, a, b, face):
        n = max(2, int(math.dist(a, b) / 0.05))
        return all(clear(net, a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n,
                         STUB / 2, face) for i in range(1, n))

    # hole-to-hole spacing applies between vias only; a BGA ball is also a "circle" obstacle,
    # and counting balls here rejected every dogbone on its own ball (0.57 mm < 0.7 mm)
    vias = {g for _, k, g, _, _ in obst if k == "circle"} - {g for _, k, g, _, _ in obst[:n_pad_obst]}
    placed, failed, shared, served = 0, [], 0, []   # served: (net, pad or via centre) on the plane
    for fp in footprints(board):
        ref = fp.GetReference()
        c = fp.GetPosition()
        cx, cy = mm(c.x) - OX, mm(c.y) - OY
        bga = ref == BGA
        for p in sorted(fp.Pads(), key=lambda q: (q.GetNumber(), q.GetPosition().x, q.GetPosition().y)):
            net = p.GetNetname()
            if net not in plane_nets or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            px, py = mm(p.GetPosition().x) - OX, mm(p.GetPosition().y) - OY
            # a pad that already holds a same-net via or track end (route_usb's ground stubs) is
            # on the plane: a second stub from the same point made an acute vertex
            if any(n == net and p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(OX + q[0]), pcbnew.FromMM(OY + q[1])))
                   for n, q in served) or any(
                    n == net and k == "seg" and (p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(OX + g[0][0]), pcbnew.FromMM(OY + g[0][1])))
                                                 or p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(OX + g[1][0]), pcbnew.FromMM(OY + g[1][1]))))
                    for n, k, g, _, _ in obst[n_pad_obst:]):
                shared += 1
                continue
            if bga:
                cands = [(px + sx * 0.4, py + sy * 0.4) for sx in (1, -1) for sy in (1, -1)]
                cands.sort(key=lambda q: (-round(math.hypot(q[0] - cx, q[1] - cy), 6), q))   # outward first
            else:
                ux, uy = px - cx, py - cy
                L = math.hypot(ux, uy) or 1.0
                ux, uy = ux / L, uy / L
                bb = p.GetBoundingBox()
                # an elongated pad (SOIC, TSOP, SOT pins) leaves along its own long axis: a stub
                # aimed away from the part centre drifts sideways into the next pin
                bw, bh = mm(bb.GetWidth()), mm(bb.GetHeight())
                if len(list(fp.Pads())) > 2 and bw > 1.3 * bh:
                    ux, uy = math.copysign(1.0, px - cx), 0.0
                elif len(list(fp.Pads())) > 2 and bh > 1.3 * bw:
                    ux, uy = 0.0, math.copysign(1.0, py - cy)
                half = max(mm(bb.GetWidth()), mm(bb.GetHeight())) / 2
                cands = []
                for d in (half + 0.45, half + 0.7, half + 1.0, half + 1.4):
                    for lat in (0, 0.5, -0.5, 1.0, -1.0):
                        cands.append((px + ux * d - uy * lat, py + uy * d + ux * lat))
            face = "B" if p.IsOnLayer(pcbnew.B_Cu) else "F"
            for vx, vy in cands:
                if not reaches_plane(net, vx, vy):
                    continue
                if any(math.hypot(hx - vx, hy - vy) < hr + VIA_DRILL / 2 + 0.4 + 0.001 for hx, hy, hr in holes):
                    continue                          # min_hole_to_hole
                if any(k == "circle" and n == net and g in vias and math.dist((vx, vy), g) < VIA_D + 0.25
                       for n, k, g, _, _ in obst):
                    continue                          # same-net vias still keep hole-to-hole
                if not clear(net, vx, vy, VIA_D / 2) or not stub_clear(net, (px, py), (vx, vy), face):
                    continue
                if any(n == net and (k == "circle" and g in vias and seg_dist(*g, (px, py), (vx, vy)) < STUB / 2
                                     or k == "seg" and collinear(g, ((px, py), (vx, vy))))
                       for n, k, g, hw, fc in obst[n_pad_obst:] if face in fc):
                    continue                          # the stub would run over a same-net via or stub
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(OX + px), pcbnew.FromMM(OY + py)))
                t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(OX + vx), pcbnew.FromMM(OY + vy)))
                t.SetWidth(pcbnew.FromMM(STUB))
                t.SetLayer(pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu)
                t.SetNet(nets[net])
                t.SetLocked(True)
                board.Add(t)
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(OX + vx), pcbnew.FromMM(OY + vy)))
                v.SetWidth(pcbnew.FromMM(VIA_D))
                v.SetDrill(pcbnew.FromMM(VIA_DRILL))
                v.SetNet(nets[net])
                v.SetLocked(True)
                board.Add(v)
                obst.append((net, "circle", (vx, vy), VIA_D / 2, FB))
                vias.add((vx, vy))
                holes.append((vx, vy, VIA_DRILL / 2))
                obst.append((net, "seg", ((px, py), (vx, vy)), STUB / 2, frozenset(face)))
                served.append((net, (px, py)))
                served.append((net, (vx, vy)))
                placed += 1
                break
            else:
                failed.append(f"{ref}.{p.GetNumber()} {net}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    print(f"fanout: {placed} pads to planes, {shared} on a neighbour's via or stub, {len(failed)} left for the router")
    for f in failed:
        print("  unfanned", f)


if __name__ == "__main__":
    main()
