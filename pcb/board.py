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
                 pad_labels=["+", "-"], pad_nets=[None, None]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="BAT",
                 pad_labels=["+", "-"], pad_nets=["VBAT", "GND"]); cx += step
board.add_jst_sh(cx, cy, pins=2, label="PA",
                 pad_labels=["+", "-"], pad_nets=["VSW", "GND"]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="PTT",
                 pad_nets=[None, "GND"]); cx += step
board.add_jst_ph(cx, cy, pins=2, label="SW",
                 pad_nets=["VBAT", "VSW"])

# Heltec V4 headers — two 18-pin rows
J3_SPAN = 17 * 2.54  # 18 pins, 17 gaps
HELTEC_WIDTH = 22.86  # distance between J3 and J2 header rows
HY = BY + BH / 2 - HELTEC_WIDTH / 2  # J3 y (top row)

board.add_header(BX + INSET + J3_SPAN / 2, HY, pins=18, label="J3",
                 pad_labels=["GND", "3V3b", "3V3a", "GPIO37", "GPIO46", "GPIO45",
                             "GPIO42", "GPIO41", "GPIO40", "GPIO39", "GPIO38", "GPIO1",
                             "GPIO2", "GPIO3", "GPIO4", "GPIO5", "GPIO6", "GPIO7"],
                 pad_nets=["GND", "VSW", "3V3", None, None, None,
                           None, None, None, None, None, None,
                           None, "BCLK", "LRC", "DIN", None, None])

# Heltec V4 J2 header (right side, pin 18→1 top to bottom)
J2_SPAN = J3_SPAN  # same 18 pins
board.add_header(BX + INSET + J2_SPAN / 2, HY + HELTEC_WIDTH, pins=18, label="J2",
                 pad_labels=["GND", "5V", "Ve_a", "Ve_b", "GPIO44", "GPIO43",
                             "RST", "GPIO0", "GPIO36", "GPIO35", "GPIO34", "GPIO33",
                             "GPIO47", "GPIO48", "GPIO26", "GPIO21", "GPIO20", "GPIO19"],
                 pad_nets=["GND", None, None, None, None, None,
                           None, None, None, None, None, None,
                           None, None, None, None, None, None])

# Board headers along bottom edge
board.add_header(BX + BW / 2, BY + BH - 5, pins=5, label="MIC",
                 pad_labels=["OUT", "GND", "VDD", "AR", "GAIN"],
                 pad_nets=[None, "GND", "3V3", None, None])
board.add_header(BX + 15, BY + BH - 5, pins=7, label="AMP",
                 pad_labels=["Vin", "GND", "SD", "GAIN", "DIN", "BCLK", "LRC"],
                 pad_nets=["3V3", "GND", None, None, "DIN", "BCLK", "LRC"])

board.save("loraudio.kicad_pcb")
