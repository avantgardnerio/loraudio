#!/usr/bin/env python3
"""Generate the open-oswst PCB."""

import subprocess
from kicad import Board

board = Board()
git_sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()

# 70x50mm landscape, centered on A4 (297x210mm)
BX, BY = 113, 113  # board origin
BW, BH = 70, 50    # board size
INSET_LR = 5        # hole center distance from left/right edges
INSET_TB = 2.5      # hole center distance from top/bottom edges

board.add_rect(BX, BY, BW, BH)

for x in (BX + INSET_LR, BX + BW - INSET_LR):
    for y in (BY + INSET_TB, BY + BH - INSET_TB):
        board.add_mounting_hole(x, y, drill=2.2)

# Connectors along top edge — fit between drill holes (INSET_LR)
cx, cy = BX + INSET_LR + 7, BY + 5
board.add_jst_ph(cx, cy, pins=2, label="BAT",
                 pad_labels=["+", "-"], pad_nets=["VBAT", "GND"]); cx += 7
board.add_jst_ph(cx, cy, pins=2, label="SW",
                 pad_nets=["VBAT", "VSW"]); cx += 7
board.add_jst_ph(cx, cy, pins=2, label="PA",
                 pad_labels=["+", "-"], pad_nets=["VSW", "GND"]); cx += 7
board.add_jst_ph(cx, cy, pins=2, label="PTT",
                 pad_nets=["PTT", "GND"]); cx += 10
board.add_jst_ph(cx, cy, pins=4, label="VOL",
                 pad_labels=["A", "B", "SW", "GND"],
                 pad_nets=["VOL_A", "VOL_B", "VOL_SW", "GND"]); cx += 11
board.add_jst_ph(cx, cy, pins=4, label="CHNL",
                 pad_labels=["A", "B", "SW", "GND"],
                 pad_nets=["CHNL_A", "CHNL_B", "CHNL_SW", "GND"])

# SPK connector on right edge (rotated 90°, near AMP)
board.add_jst_ph(BX + BW - 5, BY + INSET_TB + 7, pins=2, label="SPK", angle=90,
                 pad_labels=["-", "+"], pad_nets=["SPK-", "SPK+"])

# Heltec V4 headers — two 18-pin rows
J3_SPAN = 17 * 2.54  # 18 pins, 17 gaps
HELTEC_WIDTH = 22.86  # distance between J3 and J2 header rows
HY = BY + BH / 2 - HELTEC_WIDTH / 2  # J3 y (top row)

board.add_header(BX + 3 + J3_SPAN / 2, HY, pins=18, label="J3",
                 pad_labels=["GND", "3V3b", "3V3a", "GPIO37", "GPIO46", "GPIO45",
                             "GPIO42", "GPIO41", "GPIO40", "GPIO39", "GPIO38", "GPIO1",
                             "GPIO2", "GPIO3", "GPIO4", "GPIO5", "GPIO6", "GPIO7"],
                 pad_nets=["GND", "VSW", "3V3", None, None, None,
                           None, None, None, None, None, "VOL_A",
                           "VOL_B", "VOL_SW", "MIC_OUT", "CHNL_A", "CHNL_B", "CHNL_SW"])

# Heltec V4 J2 header (right side, pin 18→1 top to bottom)
J2_SPAN = J3_SPAN  # same 18 pins
board.add_header(BX + 3 + J2_SPAN / 2, HY + HELTEC_WIDTH, pins=18, label="J2",
                 pad_labels=["GND", "5V", "Ve_a", "Ve_b", "GPIO44", "GPIO43",
                             "RST", "GPIO0", "GPIO36", "GPIO35", "GPIO34", "GPIO33",
                             "GPIO47", "GPIO48", "GPIO26", "GPIO21", "GPIO20", "GPIO19"],
                 pad_nets=["GND", None, None, None, None, None,
                           None, "PTT", None, None, None, "BCLK",
                           "LRC", "DIN", None, None, None, None])

# Board headers along bottom edge
board.add_header(BX + BW / 2, BY + BH - 5, pins=5, label="MIC",
                 pad_labels=["GND", "VDD", "GAIN", "OUT", "AR"],
                 pad_nets=["GND", "3V3", None, "MIC_OUT", None])
AMP_X = BX + BW - 3 - 3 * 2.54
AMP_Y = BY + BH - 3 - 5
board.add_header(AMP_X, AMP_Y, pins=7, label="AMP", angle=180,
                 pad_labels=["Vin", "GND", "SD", "GAIN", "DIN", "BCLK", "LRC"],
                 pad_nets=["3V3", "GND", None, None, "DIN", "BCLK", "LRC"])
board.add_header(AMP_X, AMP_Y - 12.954, pins=2, label="AMP_SPK", angle=180,
                 pitch=3.5, pad_labels=["+", "-"], pad_nets=["SPK+", "SPK-"])

# Silkscreen — project name and git SHA
board.add_text(BX + BW / 2, BY + BH - 2, f"open-oswst  {git_sha}", size=0.8, thickness=0.12)

# Ground plane — GND zone covering full board, both copper layers
board.add_zone("GND", [
    (BX, BY), (BX + BW, BY), (BX + BW, BY + BH), (BX, BY + BH),
], clearance=0.25, thermal_gap=0.3, thermal_bridge_width=0.3)

board.save("open-oswst.kicad_pcb")
