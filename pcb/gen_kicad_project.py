#!/usr/bin/env python3
"""Generate a minimal KiCad 8 project file."""

import json
import sys

PROJECT_NAME = "loraudio"

pcb = """(kicad_pcb
  (version 20240108)
  (generator "gen_kicad_project.py")
  (generator_version "8.0")
  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (44 "Edge.Cuts" user)
  )
  (setup
    (pad_to_mask_clearance 0)
  )
  (net 0 "")

  (gr_rect (start 113 113) (end 183 163) (stroke (width 0.1) (type solid)) (fill none) (layer "Edge.Cuts"))
)
"""

pcb_out = f"{PROJECT_NAME}.kicad_pcb"
with open(pcb_out, "w") as f:
    f.write(pcb)
print(f"Wrote {pcb_out}")
