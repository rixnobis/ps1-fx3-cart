#!/usr/bin/env python3
"""Convert one package of an EAGLE .lbr into a KiCad footprint.

Usage: eagle_pkg.py <lib.lbr> <package> <out.kicad_mod>
Copies pads (PTH, round), non-plated holes and the tPlace silkscreen lines; EAGLE's y axis
points up, KiCad's down, so y is negated. Arcs on tPlace are drawn as straight chords. The
courtyard is the bounding box of every copied item plus 0.25 mm.
"""
import sys
import xml.etree.ElementTree as ET

lbr, name, out = sys.argv[1:4]
pkg = [p for p in ET.parse(lbr).getroot().iter("package") if p.get("name") == name]
assert len(pkg) == 1, (name, len(pkg))
pkg = pkg[0]
f = lambda v: float(v)  # noqa: E731
lines, xs, ys = [], [], []
for p in pkg.findall("pad"):
    x, y, d = f(p.get("x")), -f(p.get("y")), f(p.get("drill"))
    dia = f(p.get("diameter")) if p.get("diameter") else d * 1.6
    xs += [x - dia / 2, x + dia / 2]
    ys += [y - dia / 2, y + dia / 2]
    lines.append(f'  (pad "{p.get("name")}" thru_hole circle (at {x:g} {y:g}) (size {dia:g} {dia:g}) '
                 f'(drill {d:g}) (layers "*.Cu" "*.Mask"))')
for h in pkg.findall("hole"):
    x, y, d = f(h.get("x")), -f(h.get("y")), f(h.get("drill"))
    xs += [x - d / 2, x + d / 2]
    ys += [y - d / 2, y + d / 2]
    lines.append(f'  (pad "" np_thru_hole circle (at {x:g} {y:g}) (size {d:g} {d:g}) (drill {d:g}) '
                 f'(layers "*.Cu" "*.Mask"))')
for w in pkg.findall("wire"):
    if w.get("layer") != "21":
        continue
    x1, y1, x2, y2 = f(w.get("x1")), -f(w.get("y1")), f(w.get("x2")), -f(w.get("y2"))
    xs += [x1, x2]
    ys += [y1, y2]
    lines.append(f'  (fp_line (start {x1:g} {y1:g}) (end {x2:g} {y2:g}) '
                 f'(stroke (width {f(w.get("width")):g}) (type solid)) (layer "F.SilkS"))')
x0, x1, y0, y1 = min(xs) - 0.25, max(xs) + 0.25, min(ys) - 0.25, max(ys) + 0.25
lines.append(f'  (fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) '
             f'(stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))')
head = (f'(footprint "{name}" (version 20240108) (generator "eagle_pkg.py") (layer "F.Cu")\n'
        f'  (descr "{name} from {lbr.split("/")[-1]}")\n  (attr through_hole)\n'
        f'  (property "Reference" "REF**" (at 0 {y0 - 1.5:.2f} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
        f'  (property "Value" "{name}" (at 0 {y1 + 1.5:.2f} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n')
open(out, "w").write(head + "\n".join(lines) + "\n)\n")
print(f"{out}: {len(pkg.findall('pad'))} pads, {len(pkg.findall('hole'))} holes, courtyard {x1 - x0:.2f} x {y1 - y0:.2f} mm")
