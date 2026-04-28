"""OSWST case — hello world box, two-piece (bottom + lid)."""

from build123d import *

# Overall dimensions
WIDTH = 72
LENGTH = 110
HEIGHT = 30
WALL = 2
FILLET_R = 3
LID_HEIGHT = 8  # how much of the total height is lid

# Full outer shell
outer = Box(WIDTH, LENGTH, HEIGHT)
outer = fillet(outer.edges(), radius=FILLET_R)

# Split into bottom and lid using bisect
split_z = HEIGHT / 2 - LID_HEIGHT  # Z=0 is center, so split plane in world coords

bottom = split(outer, Plane(origin=(0, 0, split_z), z_dir=(0, 0, 1)), keep=Keep.BOTTOM)
lid = split(outer, Plane(origin=(0, 0, split_z), z_dir=(0, 0, 1)), keep=Keep.TOP)

# Hollow both — open at the split face
bottom_top_face = bottom.faces().sort_by(Axis.Z)[-1]
bottom = offset(bottom, amount=-WALL, openings=[bottom_top_face])

lid_bottom_face = lid.faces().sort_by(Axis.Z)[0]
lid = offset(lid, amount=-WALL, openings=[lid_bottom_face])

# Move both onto the bed (Z=0) and place lid next to bottom
bottom = Pos(0, 0, -bottom.bounding_box().min.Z) * bottom
lid = Pos(WIDTH + 5, 0, -lid.bounding_box().min.Z) * lid

# Combine into single print plate
plate = Compound(children=[bottom, lid])

# Export
export_step(plate, "models/case.step")
export_stl(plate, "models/case.stl")
print(f"Exported case: {WIDTH}x{LENGTH}x{HEIGHT}mm, lid={LID_HEIGHT}mm, wall={WALL}mm")
