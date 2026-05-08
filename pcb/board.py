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

# Speaker connector (JST-PH 2-pin SMD)
board.add_jst_ph(BX + 35, BY + 5, pins=2, label="SPK", pad_labels=["+", "-"])

board.save("loraudio.kicad_pcb")
