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
board.add_jst_ph(cx, cy, pins=2, label="SPK",
                 pad_labels=["+", "-"], pad_nets=["SPK+", "GND"]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="BAT",
                 pad_labels=["+", "-"], pad_nets=["VBAT", "GND"]); cx += step
board.add_jst_sh(cx, cy, pins=2, label="PA",
                 pad_labels=["+", "-"], pad_nets=["VBAT", "GND"]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="PTT",
                 pad_nets=["PTT", "GND"]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="PWR",
                 pad_nets=["VBAT", "PWR_SW"])

# Board headers along bottom edge
board.add_header(BX + BW / 2, BY + BH - 5, pins=5, label="MIC",
                 pad_labels=["OUT", "GND", "VDD", "AR", "GAIN"],
                 pad_nets=["MIC_OUT", "GND", "VBAT", None, None])
board.add_header(BX + 15, BY + BH - 5, pins=7, label="AMP",
                 pad_labels=["Vin", "GND", "SD", "GAIN", "DIN", "BCLK", "LRC"],
                 pad_nets=["VBAT", "GND", None, None, "I2S_DIN", "I2S_BCLK", "I2S_LRC"])

board.save("loraudio.kicad_pcb")
