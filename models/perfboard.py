#!/usr/bin/env python3
"""Stripboard layout tool for the GENNEL 70×50mm perfboard.

Generates a dual-view SVG (component side + copper side) showing
component placement, trace cuts, jumpers, and labels.

Run: source .venv/bin/activate && python models/perfboard.py
Output: models/perfboard.svg
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# Board geometry — GENNEL 70×50mm stripboard
PITCH = 2.54  # mm hole-to-hole
COLS = 26     # 70mm / 2.54 ≈ 27, but edge margins → 26 usable
ROWS = 18     # 50mm / 2.54 ≈ 19, but edge margins → 18 usable

# SVG rendering constants
SCALE = 8          # px per mm
HOLE_R = 0.4       # mm radius of hole
PAD_R = 0.9        # mm radius of copper pad
TRACE_W = 0.6      # mm width of copper trace between pads
MARGIN = 8         # mm margin around board in SVG
BOARD_W = (COLS - 1) * PITCH + 2 * MARGIN
BOARD_H = (ROWS - 1) * PITCH + 2 * MARGIN
GAP = 12           # mm gap between top and bottom views
LABEL_AREA = 6     # mm for row/col labels


@dataclass
class Component:
    name: str
    row: int          # top-left row (0-indexed)
    col: int          # top-left col (0-indexed)
    rows: int         # height in holes
    cols: int         # width in holes
    color: str = "#4488cc"
    pins: dict = field(default_factory=dict)  # {pin_name: (row_offset, col_offset)}


@dataclass
class Cut:
    row: int
    col: int


@dataclass
class Jumper:
    r1: int
    c1: int
    r2: int
    c2: int
    color: str = "#ff8800"


@dataclass
class Label:
    row: int
    col: int
    text: str
    rotation: float = 0
    anchor: str = "middle"


class Stripboard:
    """Represents a stripboard layout with components, cuts, and jumpers."""

    def __init__(self, cols: int = COLS, rows: int = ROWS):
        self.cols = cols
        self.rows = rows
        self.components: list[Component] = []
        self.cuts: list[Cut] = []
        self.jumpers: list[Jumper] = []
        self.labels: list[Label] = []

    def component(
        self,
        name: str,
        row: int,
        col: int,
        rows: int,
        cols: int,
        color: str = "#4488cc",
        pins: dict | None = None,
    ) -> Component:
        """Place a rectangular component on the board."""
        c = Component(name, row, col, rows, cols, color, pins or {})
        self.components.append(c)
        return c

    def cut(self, row: int, col: int) -> Cut:
        """Break the copper trace at (row, col)."""
        c = Cut(row, col)
        self.cuts.append(c)
        return c

    def jumper(
        self, r1: int, c1: int, r2: int, c2: int, color: str = "#ff8800"
    ) -> Jumper:
        """Add a wire jumper between two holes."""
        j = Jumper(r1, c1, r2, c2, color)
        self.jumpers.append(j)
        return j

    def label(self, row: int, col: int, text: str, rotation: float = 0, anchor: str = "middle") -> Label:
        """Add a text annotation near a hole."""
        lbl = Label(row, col, text, rotation, anchor)
        self.labels.append(lbl)
        return lbl

    # ── SVG rendering ──────────────────────────────────────────────

    def _hole_pos(self, row: int, col: int, mirror: bool = False) -> tuple[float, float]:
        """Convert grid coords to mm position within a board view.
        If mirror=True, flip columns (copper side = horizontally mirrored)."""
        c = (self.cols - 1 - col) if mirror else col
        x = LABEL_AREA + MARGIN + c * PITCH
        y = LABEL_AREA + MARGIN + row * PITCH
        return x, y

    def _svg_board_outline(self, parent: ET.Element, ox: float, oy: float):
        """Draw the PCB outline rectangle."""
        x = ox + LABEL_AREA
        y = oy + LABEL_AREA
        w = (self.cols - 1) * PITCH + 2 * MARGIN
        h = (self.rows - 1) * PITCH + 2 * MARGIN
        ET.SubElement(parent, "rect", {
            "x": f"{x:.2f}", "y": f"{y:.2f}",
            "width": f"{w:.2f}", "height": f"{h:.2f}",
            "fill": "#f5f0e0", "stroke": "#888", "stroke-width": "0.3",
            "rx": "1",
        })

    def _svg_grid_labels(self, parent: ET.Element, ox: float, oy: float, mirror: bool = False):
        """Draw row/col index labels. Columns use letters (A-Z), rows use numbers."""
        for c in range(self.cols):
            display_col = (self.cols - 1 - c) if mirror else c
            hx, _ = self._hole_pos(0, c)
            ET.SubElement(parent, "text", {
                "x": f"{ox + hx:.2f}",
                "y": f"{oy + LABEL_AREA - 1:.2f}",
                "text-anchor": "middle",
                "font-size": "2.2",
                "font-family": "monospace",
                "fill": "#666",
            }).text = chr(ord('A') + display_col)
        for r in range(self.rows):
            _, hy = self._hole_pos(r, 0)
            ET.SubElement(parent, "text", {
                "x": f"{ox + LABEL_AREA - 1:.2f}",
                "y": f"{oy + hy + 0.8:.2f}",
                "text-anchor": "middle",
                "font-size": "2.2",
                "font-family": "monospace",
                "fill": "#666",
            }).text = str(r)

    def _svg_copper_traces(self, parent: ET.Element, ox: float, oy: float, mirror: bool = False):
        """Draw horizontal copper traces with cuts applied."""
        cut_set = {(c.row, c.col) for c in self.cuts}
        for r in range(self.rows):
            # Build segments: a cut at col C breaks the trace between C-1 and C
            segments = []
            seg_start = 0
            for c in range(self.cols):
                if (r, c) in cut_set:
                    if c > seg_start:
                        segments.append((seg_start, c - 1))
                    seg_start = c + 1
            if seg_start < self.cols:
                segments.append((seg_start, self.cols - 1))
            for c_start, c_end in segments:
                if c_start == c_end:
                    continue  # single pad, no trace segment to draw
                x1, y1 = self._hole_pos(r, c_start, mirror)
                x2, _ = self._hole_pos(r, c_end, mirror)
                ET.SubElement(parent, "line", {
                    "x1": f"{ox + x1:.2f}", "y1": f"{oy + y1:.2f}",
                    "x2": f"{ox + x2:.2f}", "y2": f"{oy + y1:.2f}",
                    "stroke": "#cc8833", "stroke-width": f"{TRACE_W:.2f}",
                    "stroke-linecap": "round",
                })

    def _svg_pads_and_holes(self, parent: ET.Element, ox: float, oy: float, copper: bool, mirror: bool = False):
        """Draw pads (copper side) or holes (component side)."""
        for r in range(self.rows):
            for c in range(self.cols):
                hx, hy = self._hole_pos(r, c, mirror)
                x, y = ox + hx, oy + hy
                if copper:
                    # Copper pad
                    ET.SubElement(parent, "circle", {
                        "cx": f"{x:.2f}", "cy": f"{y:.2f}",
                        "r": f"{PAD_R:.2f}",
                        "fill": "#cc8833", "stroke": "none",
                    })
                # Drill hole
                ET.SubElement(parent, "circle", {
                    "cx": f"{x:.2f}", "cy": f"{y:.2f}",
                    "r": f"{HOLE_R:.2f}",
                    "fill": "#f5f0e0" if copper else "#ddd8c8",
                    "stroke": "#999" if not copper else "none",
                    "stroke-width": "0.1",
                })

    def _svg_cuts(self, parent: ET.Element, ox: float, oy: float, mirror: bool = False):
        """Draw X marks for trace cuts (copper side only)."""
        d = PAD_R * 0.7
        for cut in self.cuts:
            hx, hy = self._hole_pos(cut.row, cut.col, mirror)
            x, y = ox + hx, oy + hy
            for dx, dy in [(d, d), (d, -d)]:
                ET.SubElement(parent, "line", {
                    "x1": f"{x - dx:.2f}", "y1": f"{y - dy:.2f}",
                    "x2": f"{x + dx:.2f}", "y2": f"{y + dy:.2f}",
                    "stroke": "#ee2222", "stroke-width": "0.4",
                    "stroke-linecap": "round",
                })

    def _svg_components(self, parent: ET.Element, ox: float, oy: float):
        """Draw component outlines, names, and pin circles (not pin labels)."""
        for comp in self.components:
            x1, y1 = self._hole_pos(comp.row, comp.col)
            x2, y2 = self._hole_pos(comp.row + comp.rows - 1, comp.col + comp.cols - 1)
            pad = PITCH * 0.35
            rx, ry = ox + x1 - pad, oy + y1 - pad
            rw, rh = (x2 - x1) + 2 * pad, (y2 - y1) + 2 * pad
            ET.SubElement(parent, "rect", {
                "x": f"{rx:.2f}", "y": f"{ry:.2f}",
                "width": f"{rw:.2f}", "height": f"{rh:.2f}",
                "fill": comp.color, "fill-opacity": "0.25",
                "stroke": comp.color, "stroke-width": "0.3",
                "rx": "0.5",
            })
            # Component name centered
            cx = rx + rw / 2
            cy = ry + rh / 2
            ET.SubElement(parent, "text", {
                "x": f"{cx:.2f}", "y": f"{cy + 0.8:.2f}",
                "text-anchor": "middle",
                "font-size": "2.5",
                "font-family": "sans-serif",
                "font-weight": "bold",
                "fill": comp.color,
            }).text = comp.name
            # Pin marker circles
            for pin_name, (pr, pc) in comp.pins.items():
                px, py = self._hole_pos(comp.row + pr, comp.col + pc)
                ET.SubElement(parent, "circle", {
                    "cx": f"{ox + px:.2f}", "cy": f"{oy + py:.2f}",
                    "r": f"{HOLE_R + 0.2:.2f}",
                    "fill": "none", "stroke": comp.color, "stroke-width": "0.2",
                })

    def _svg_pin_labels(self, parent: ET.Element, ox: float, oy: float):
        """Draw pin labels facing inward toward component center."""
        for comp in self.components:
            # Count how many pins share each row and column
            from collections import Counter
            row_counts = Counter(pr for pr, pc in comp.pins.values())
            col_counts = Counter(pc for pr, pc in comp.pins.values())

            for pin_name, (pr, pc) in comp.pins.items():
                px, py = self._hole_pos(comp.row + pr, comp.col + pc)
                # Horizontal run → vertical label, vertical run → horizontal label
                if row_counts[pr] >= col_counts[pc]:
                    # Pin is part of a horizontal row → label vertically
                    if pr < comp.rows / 2:  # top half → point down
                        tx, ty = ox + px, oy + py + 1.2
                        rot, anchor = 90, "start"
                    else:                   # bottom half → point up
                        tx, ty = ox + px, oy + py - 1.2
                        rot, anchor = -90, "start"
                else:
                    # Pin is part of a vertical column → label horizontally
                    if pc < comp.cols / 2:  # left half → point right
                        tx, ty = ox + px + 1.2, oy + py + 0.5
                        rot, anchor = None, "start"
                    else:                   # right half → point left
                        tx, ty = ox + px - 1.2, oy + py + 0.5
                        rot, anchor = None, "end"
                attrs = {
                    "x": f"{tx:.2f}", "y": f"{ty:.2f}",
                    "text-anchor": anchor,
                    "font-size": "1.5",
                    "font-family": "monospace",
                    "font-weight": "bold",
                    "fill": "#111",
                }
                if rot is not None:
                    attrs["transform"] = f"rotate({rot}, {tx:.2f}, {ty:.2f})"
                ET.SubElement(parent, "text", attrs).text = pin_name

    def _svg_jumpers(self, parent: ET.Element, ox: float, oy: float):
        """Draw wire jumpers."""
        for j in self.jumpers:
            x1, y1 = self._hole_pos(j.r1, j.c1)
            x2, y2 = self._hole_pos(j.r2, j.c2)
            ET.SubElement(parent, "line", {
                "x1": f"{ox + x1:.2f}", "y1": f"{oy + y1:.2f}",
                "x2": f"{ox + x2:.2f}", "y2": f"{oy + y2:.2f}",
                "stroke": j.color, "stroke-width": "0.5",
                "stroke-linecap": "round",
                "stroke-dasharray": "1.5,0.8",
            })
            for x, y in [(ox + x1, oy + y1), (ox + x2, oy + y2)]:
                ET.SubElement(parent, "circle", {
                    "cx": f"{x:.2f}", "cy": f"{y:.2f}",
                    "r": "0.6",
                    "fill": j.color, "stroke": "none",
                })

    def _svg_labels(self, parent: ET.Element, ox: float, oy: float):
        """Draw user annotations."""
        for lbl in self.labels:
            hx, hy = self._hole_pos(lbl.row, lbl.col)
            tx, ty = ox + hx, oy + hy + 0.6
            attrs = {
                "x": f"{tx:.2f}", "y": f"{ty:.2f}",
                "text-anchor": lbl.anchor,
                "font-size": "1.8",
                "font-family": "sans-serif",
                "fill": "#cc3333",
            }
            if lbl.rotation:
                attrs["transform"] = f"rotate({lbl.rotation}, {tx:.2f}, {ty:.2f})"
            ET.SubElement(parent, "text", attrs).text = lbl.text

    def render_svg(self, path: str | Path):
        """Render dual-view SVG: top (component side) + bottom (copper side, mirrored)."""
        view_w = LABEL_AREA + BOARD_W
        view_h = LABEL_AREA + BOARD_H
        total_w = view_w
        total_h = view_h * 2 + GAP + 8  # 8mm for title texts
        svg_w = total_w * SCALE
        svg_h = total_h * SCALE

        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{svg_w:.0f}",
            "height": f"{svg_h:.0f}",
            "viewBox": f"0 0 {total_w:.2f} {total_h:.2f}",
        })
        # Background
        ET.SubElement(svg, "rect", {
            "width": "100%", "height": "100%", "fill": "white",
        })

        # ── Top view (component side) ──
        oy_top = 4  # leave room for title
        ET.SubElement(svg, "text", {
            "x": f"{total_w / 2:.2f}", "y": "3",
            "text-anchor": "middle",
            "font-size": "3",
            "font-family": "sans-serif",
            "font-weight": "bold",
            "fill": "#333",
        }).text = "COMPONENT SIDE (top view)"

        self._svg_board_outline(svg, 0, oy_top)
        self._svg_grid_labels(svg, 0, oy_top)
        self._svg_pads_and_holes(svg, 0, oy_top, copper=False)
        self._svg_components(svg, 0, oy_top)
        self._svg_jumpers(svg, 0, oy_top)
        self._svg_labels(svg, 0, oy_top)
        self._svg_pin_labels(svg, 0, oy_top)  # top z-order

        # ── Bottom view (copper side, mirrored horizontally) ──
        oy_bot = oy_top + view_h + GAP
        ET.SubElement(svg, "text", {
            "x": f"{total_w / 2:.2f}", "y": f"{oy_bot - 1:.2f}",
            "text-anchor": "middle",
            "font-size": "3",
            "font-family": "sans-serif",
            "font-weight": "bold",
            "fill": "#333",
        }).text = "COPPER SIDE (bottom view, mirrored)"

        # Draw copper side with mirrored column positions (no transform group needed)
        self._svg_board_outline(svg, 0, oy_bot)
        self._svg_copper_traces(svg, 0, oy_bot, mirror=True)
        self._svg_pads_and_holes(svg, 0, oy_bot, copper=True, mirror=True)
        self._svg_cuts(svg, 0, oy_bot, mirror=True)
        self._svg_grid_labels(svg, 0, oy_bot, mirror=True)

        # Write SVG
        tree = ET.ElementTree(svg)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="unicode", xml_declaration=True)
        print(f"Wrote {path}")


# ── Starter layout ─────────────────────────────────────────────────

def build_layout() -> Stripboard:
    """Create the initial OSWST perfboard layout."""
    board = Stripboard()

    # Heltec V4 mounted sideways: 51.6×25.6mm ≈ 20 cols × 10 rows
    # Placed at top of board, centered horizontally
    # Headers: J3 (left, 18 pins) and J2 (right, 18 pins) — along the long edges
    heltec = board.component(
        "Heltec V4", row=1, col=0, rows=10, cols=20,
        color="#2266aa",
        pins={
            # J3 header (top edge as placed, text readable) — pin 1 at left
            "GND":  (0, 0),   # J3 pin 1
            "3V3a": (0, 1),   # J3 pin 2
            "3V3b": (0, 2),   # J3 pin 3
            "G37":  (0, 3),   # J3 pin 4 (ADC_Ctrl)
            "G46":  (0, 4),   # J3 pin 5
            "G45":  (0, 5),   # J3 pin 6
            "G42":  (0, 6),   # J3 pin 7
            "G41":  (0, 7),   # J3 pin 8
            "G40":  (0, 8),   # J3 pin 9
            "G39":  (0, 9),   # J3 pin 10
            "G38":  (0, 10),  # J3 pin 11
            "G1":   (0, 11),  # J3 pin 12 (VBAT_Read)
            "G2":   (0, 12),  # J3 pin 13
            "G3":   (0, 13),  # J3 pin 14 (BCLK)
            "G4":   (0, 14),  # J3 pin 15 (WS)
            "G5":   (0, 15),  # J3 pin 16 (DIN)
            "G6":   (0, 16),  # J3 pin 17 (ADC mic)
            "G7":   (0, 17),  # J3 pin 18 (ADC mic alt)
            # J2 header (bottom edge as placed) — pin 1 at left
            "GND2": (9, 0),   # J2 pin 1
            "5V":   (9, 1),   # J2 pin 2
            "Ve1":  (9, 2),   # J2 pin 3
            "Ve2":  (9, 3),   # J2 pin 4
            "RX":   (9, 4),   # J2 pin 5 (GPIO44)
            "TX":   (9, 5),   # J2 pin 6 (GPIO43)
            "RST":  (9, 6),   # J2 pin 7
            "G0":   (9, 7),   # J2 pin 8 (PRG/PTT)
            "G36":  (9, 8),   # J2 pin 9 (Vext)
            "G35":  (9, 9),   # J2 pin 10 (LED)
            "G34":  (9, 10),  # J2 pin 11
            "G33":  (9, 11),  # J2 pin 12
            "G48":  (9, 12),  # J2 pin 13
            "G47":  (9, 13),  # J2 pin 14
            "G26":  (9, 14),  # J2 pin 15
            "G21":  (9, 15),  # J2 pin 16 (OLED_RST)
            "D+":   (9, 16),  # J2 pin 17 (USB D+)
            "D-":   (9, 17),  # J2 pin 18 (USB D-)
        },
    )

    # MAX98357A speaker amp — below Heltec, left side
    # ~25×13mm ≈ 10 cols × 5 rows
    board.component(
        "MAX98357A\nSpeaker Amp", row=13, col=1, rows=5, cols=10,
        color="#22aa44",
        pins={
            "LRC":  (0, 0),  # I2S word select (GPIO4)
            "BCLK": (1, 0),  # I2S bit clock (GPIO3)
            "DIN":  (2, 0),  # I2S data in (GPIO5)
            "GND":  (3, 0),  # Ground
            "Vin":  (4, 0),  # 3.3V or 5V
            "SP+":  (0, 9),  # Speaker +
            "SP-":  (1, 9),  # Speaker -
        },
    )

    # MAX9814 mic board — below Heltec, right side
    # ~25×13mm ≈ 10 cols × 5 rows
    board.component(
        "MAX9814\nMic AGC", row=13, col=14, rows=5, cols=10,
        color="#aa4422",
        pins={
            "OUT": (0, 0),  # Analog out → ADC (GPIO6 or 7)
            "GND": (1, 0),  # Ground
            "VDD": (2, 0),  # 3.3V
            "AR":  (3, 0),  # Attack/release ratio
            "G":   (4, 0),  # Gain select
        },
    )

    # Example cuts — isolate some traces between components
    # (These are placeholders; real cuts TBD when we do pin-by-pin routing)
    for c in range(0, 20):
        board.cut(12, c)  # Cut row 12 to separate Heltec from lower boards

    # Example jumpers — connect I2S signals from Heltec J3 (row 0) to speaker amp
    # Heltec J3 pins: G3=(1,13), G4=(1,14), G5=(1,15), G6=(1,16)
    # Amp pins: LRC=row13/col1, BCLK=row14/col1, DIN=row15/col1
    board.jumper(0, 13, 14, 0, "#0088ff")   # G3 (BCLK) → amp BCLK
    board.jumper(0, 14, 13, 0, "#00cc44")   # G4 (WS/LRC) → amp LRC
    board.jumper(0, 15, 15, 0, "#ff4400")   # G5 (DIN) → amp DIN
    # Mic analog out to Heltec ADC
    board.jumper(13, 13, 0, 16, "#cc44cc")  # Mic OUT → G6 (ADC)

    # Labels
    board.label(5, 0, "→ USB-C")
    board.label(12, 10, "— trace cuts —")

    return board


if __name__ == "__main__":
    board = build_layout()
    out = Path(__file__).parent / "perfboard.svg"
    board.render_svg(out)
    print(f"Open in browser: file://{out.resolve()}")
