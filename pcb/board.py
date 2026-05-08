#!/usr/bin/env python3
"""Generate the loraudio PCB."""

from kicad import Board

board = Board()

# 70x50mm landscape, centered on A4 (297x210mm)
BX, BY = 113, 113  # board origin
BW, BH = 70, 50    # board size
INSET = 3           # hole center distance from edge

board.add_rect(BX, BY, BW, BH)

for x in (BX + INSET, BX + BW - INSET):
    for y in (BY + INSET, BY + BH - INSET):
        board.add_mounting_hole(x, y)

# Connectors along top edge
cx, cy, step = BX + 14, BY + 5, 8
board.add_jst_ph(cx, cy, pins=2, label="SPK", pad_labels=["+", "-"]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="BAT", pad_labels=["+", "-"]); cx += step
board.add_jst_sh(cx, cy, pins=2, label="PA", pad_labels=["+", "-"]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="PTT"); cx += step
board.add_jst_ph(cx, cy, pins=2, label="PWR")

# Mic board header (MAX9814, 5-pin 2.54mm) centered on bottom edge
board.add_header(BX + BW / 2, BY + BH - 5, pins=5, label="MIC",
                 pad_labels=["OUT", "GND", "VDD", "AR", "GAIN"])

board.save("loraudio.kicad_pcb")
