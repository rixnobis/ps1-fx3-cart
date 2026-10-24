#!/bin/bash
# Regenerate the schematic and run every check; stops on the first failure.
# LCSC=0 skips the JLC lookups (network).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
python3 -P tools/gen_sch.py
kicad-cli sch erc --format report --exit-code-violations -o build/erc.rpt ps1-fx3-cart.kicad_sch >/dev/null
grep 'ERC messages' build/erc.rpt
kicad-cli sch export netlist --format kicadxml -o build/netlist.xml ps1-fx3-cart.kicad_sch >/dev/null
python3 -P tools/check_netlist.py build/netlist.xml
python3 -P tools/check_footprints.py build/netlist.xml
if [ "${LCSC:-1}" = 1 ]; then python3 -P tools/check_lcsc.py build/netlist.xml; fi
kicad-cli sch export pdf -o schematic.pdf ps1-fx3-cart.kicad_sch >/dev/null
python3 -P tools/build_pcb.py place 2> >(grep -v "swig/python detected" >&2)
echo "build ok"
