#!/usr/bin/env python3
"""Generate the loraudio PCB."""

from kicad import Board

board = Board()

# 70x50mm landscape, centered on A4 (297x210mm)
board.add_rect(113, 113, 70, 50)

board.save("loraudio.kicad_pcb")
