"""Minimal KiCad PCB file generator."""


class Board:
    def __init__(self, paper="A4", thickness=1.6):
        self.paper = paper
        self.thickness = thickness
        self.layers = [
            (0, "F.Cu", "signal", None),
            (31, "B.Cu", "signal", None),
            (36, "B.SilkS", "user", "B.Silkscreen"),
            (37, "F.SilkS", "user", "F.Silkscreen"),
            (44, "Edge.Cuts", "user", None),
        ]
        self.graphics = []
        self.footprints = []
        self._fp_id = 0

    def add_rect(self, x, y, w, h, layer="Edge.Cuts", width=0.1):
        self.graphics.append(
            f'  (gr_rect (start {x} {y}) (end {x+w} {y+h})'
            f' (stroke (width {width}) (type solid)) (fill none)'
            f' (layer "{layer}"))'
        )

    def add_mounting_hole(self, x, y, drill=3.2):
        """Add a non-plated through-hole at (x, y) with given drill diameter in mm."""
        self._fp_id += 1
        pad_size = drill + 0.5
        self.footprints.append(
            f'  (footprint "MountingHole_{drill}mm"\n'
            f'    (layer "F.Cu")\n'
            f"    (at {x} {y})\n"
            f'    (attr exclude_from_pos_files exclude_from_bom)\n'
            f'    (fp_text reference "" (at 0 0) (layer "F.SilkS") hide\n'
            f"      (effects (font (size 1 1) (thickness 0.15)))\n"
            f"    )\n"
            f'    (pad "" np_thru_hole circle\n'
            f"      (at 0 0)\n"
            f"      (size {pad_size} {pad_size})\n"
            f"      (drill {drill})\n"
            f"      (layers *.Cu *.Mask)\n"
            f"    )\n"
            f"  )"
        )

    def add_jst_ph(self, x, y, pins=2, label="", angle=0, pad_labels=None):
        """Add a JST-PH through-hole header (2.0mm pitch) at (x, y).

        Pads are numbered 1..pins, spaced 2.0mm apart, centered on (x, y).
        Through-hole pins with 0.8mm drill, 1.5mm annular pad.
        pad_labels: optional list of strings to label each pad (e.g. ["+", "-"]).
        """
        self._fp_id += 1
        pitch = 2.0
        pad_size = 1.5
        drill = 0.8
        half_span = pitch * (pins - 1) / 2

        pad_lines = []
        for i in range(pins):
            px = -half_span + i * pitch
            pad_name = pad_labels[i] if pad_labels and i < len(pad_labels) else str(i + 1)
            pad_lines.append(
                f'    (pad "{pad_name}" thru_hole circle\n'
                f"      (at {px} 0)\n"
                f"      (size {pad_size} {pad_size})\n"
                f"      (drill {drill})\n"
                f"      (layers *.Cu *.Mask)\n"
                f"    )"
            )

        pads = "\n".join(pad_lines)
        ref_text = label or f"J{self._fp_id}"
        at_str = f"(at {x} {y})" if angle == 0 else f"(at {x} {y} {angle})"
        self.footprints.append(
            f'  (footprint "JST_PH_B{pins}B"\n'
            f'    (layer "F.Cu")\n'
            f"    {at_str}\n"
            f'    (fp_text reference "{ref_text}" (at 0 -2.5) (layer "F.SilkS")\n'
            f"      (effects (font (size 1 1) (thickness 0.15)))\n"
            f"    )\n"
            f"{pads}\n"
            f"  )"
        )

    def _render_layers(self):
        lines = []
        for num, name, kind, alias in self.layers:
            if alias:
                lines.append(f'    ({num} "{name}" {kind} "{alias}")')
            else:
                lines.append(f'    ({num} "{name}" {kind})')
        return "\n".join(lines)

    def render(self):
        parts = []
        if self.graphics:
            parts.append("\n".join(self.graphics))
        if self.footprints:
            parts.append("\n".join(self.footprints))
        gfx = "\n\n" + "\n\n".join(parts) if parts else ""
        return (
            f"(kicad_pcb\n"
            f'  (version 20240108)\n'
            f'  (generator "kicad.py")\n'
            f'  (generator_version "8.0")\n'
            f"  (general\n"
            f"    (thickness {self.thickness})\n"
            f"    (legacy_teardrops no)\n"
            f"  )\n"
            f'  (paper "{self.paper}")\n'
            f"  (layers\n"
            f"{self._render_layers()}\n"
            f"  )\n"
            f"  (setup\n"
            f"    (pad_to_mask_clearance 0)\n"
            f"  )\n"
            f'  (net 0 "")'
            f"{gfx}\n"
            f")\n"
        )

    def save(self, path):
        with open(path, "w") as f:
            f.write(self.render())
        print(f"Wrote {path}")
