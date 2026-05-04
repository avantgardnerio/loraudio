"""OSWST case — hello world box, two-piece (bottom + lid)."""

from build123d import *
from pathlib import Path

OUT = Path(__file__).parent

# Overall dimensions
WIDTH = 80
LENGTH = 145
HEIGHT = 30
WALL = 2
FILLET_R = 3
LID_HEIGHT = 4  # how much of the total height is lid

# Amp screw post
AMP_POST_FROM_TOP = 8.5    # mm from top inside wall (Y axis)
AMP_POST_FROM_LEFT = 13    # mm from left inside wall (X axis)
AMP_POST_HEIGHT = 18      # tops sit 6mm below case side tops
AMP_POST_OD = 5            # outer diameter
AMP_POST_ID = 1.8          # pilot hole for M2 screw

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

# Screw post locations
floor_z = -HEIGHT / 2 + WALL
OVERLAP = 0.5  # sink into floor for clean boolean fusion

# Amp posts — positioned from inside walls
post_x = -(WIDTH / 2 - WALL - AMP_POST_FROM_LEFT)
post_y1 = LENGTH / 2 - WALL - AMP_POST_FROM_TOP
post_y2 = post_y1 - 35.5  # 2nd post 35.5mm below (moved down 1 radius to clear module)

# Perfboard posts — 50x70mm board, landscape (70mm across width, 50mm along length)
PERF_W = 70
PERF_L = 50
PERF_HOLE_FROM_LR = 5      # mm from left & right edges of board
PERF_HOLE_FROM_TB = 2.5    # mm from top & bottom edges of board
PERF_POST_HEIGHT = 6
PERF_GAP_FROM_AMP = 28     # mm below lower amp post

perf_center_y = post_y2 - PERF_GAP_FROM_AMP - PERF_L / 2
perf_center_x = 0  # centered in case

# Collect all post locations: (x, y, height)
all_posts = []
for py in [post_y1, post_y2]:
    all_posts.append((post_x, py, AMP_POST_HEIGHT))
for px in [perf_center_x - PERF_W / 2 + PERF_HOLE_FROM_LR,
           perf_center_x + PERF_W / 2 - PERF_HOLE_FROM_LR]:
    for py in [perf_center_y + PERF_L / 2 - PERF_HOLE_FROM_TB,
               perf_center_y - PERF_L / 2 + PERF_HOLE_FROM_TB]:
        all_posts.append((px, py, PERF_POST_HEIGHT))

# Add all posts then drill all holes
posts_solid = None
for px, py, h in all_posts:
    cz = floor_z + (h - OVERLAP) / 2
    post = Pos(px, py, cz) * Cylinder(radius=AMP_POST_OD / 2, height=h + OVERLAP)
    posts_solid = post if posts_solid is None else (posts_solid + post)

holes_solid = None
for px, py, h in all_posts:
    cz = floor_z + h / 2
    hole = Pos(px, py, cz) * Cylinder(radius=AMP_POST_ID / 2, height=h + 1)
    holes_solid = hole if holes_solid is None else (holes_solid + hole)

result = bottom + posts_solid - holes_solid
bottom = result.solids()[0] if hasattr(result, 'solids') else result

# SMA hole through top wall (positive Y), aligned with raised amp posts
SMA_HOLE_DIA = 7.0
sma_z = floor_z + AMP_POST_HEIGHT  # top of raised amp posts
sma_hole = Pos(post_x - 5, LENGTH / 2, sma_z) * Rot(90, 0, 0) * Cylinder(
    radius=SMA_HOLE_DIA / 2, height=WALL * 3
)
bottom = bottom - sma_hole

# Top wall controls — laid out right of antenna (positive X direction)
# Antenna right edge is at post_x + 6.5 (13mm dia)
ant_right_x = post_x + 6.5 - 5  # shifted 5mm left to clear screw post
controls_z = floor_z + 11  # original control height — independent of raised amp/SMA

# Power slider cutout: 11x6mm hole, 20mm total with screwdowns
SLIDER_W = 12   # along X (slide direction) — 1mm clearance to screw holes at ±7mm
SLIDER_H = 8    # along Z
slider_center_x = ant_right_x + 20 / 2  # 20mm footprint starts at antenna edge

# Encoder holes: 7mm dia, 15mm knobs, 3mm gap between knobs
ENCODER_DIA = 7.2
KNOB_DIA = 15
KNOB_GAP = 3
enc1_center_x = ant_right_x + 20 + KNOB_GAP + KNOB_DIA / 2
enc2_center_x = enc1_center_x + KNOB_DIA / 2 + KNOB_GAP + KNOB_DIA / 2

# Cut slider
slider_hole = Pos(slider_center_x, LENGTH / 2, controls_z) * Rot(90, 0, 0) * Box(
    SLIDER_W, WALL * 3, SLIDER_H
)
bottom = bottom - slider_hole

# Power switch screw holes, 14mm apart
SLIDER_SCREW_SPACING = 14
for sx in [-1, +1]:
    screw = Pos(slider_center_x + sx * SLIDER_SCREW_SPACING / 2, LENGTH / 2, controls_z) * Rot(90, 0, 0) * Cylinder(
        radius=AMP_POST_ID / 2, height=WALL * 3
    )
    bottom = bottom - screw

# Cut encoder holes
for enc_x in [enc1_center_x, enc2_center_x]:
    enc_hole = Pos(enc_x, LENGTH / 2, controls_z) * Rot(90, 0, 0) * Cylinder(
        radius=ENCODER_DIA / 2, height=WALL * 3
    )
    bottom = bottom - enc_hole

# PTT button hole through right wall (positive X), 13mm from top wall
PTT_DIA = 16.5
ptt_y = LENGTH / 2 - 23  # 23mm from top (antenna end) — shifted 8mm toward encoders
ptt_z = (floor_z + split_z) / 2  # centered on usable wall height
ptt_hole = Pos(WIDTH / 2, ptt_y, ptt_z) * Rot(0, 90, 0) * Cylinder(
    radius=PTT_DIA / 2, height=WALL * 3
)
bottom = bottom - ptt_hole

# Kenwood jack through left wall (negative X), 3.5mm on top, 2.5mm below, 12mm apart
KENWOOD_SPACING = 12
kenwood_y_top = -(LENGTH / 2 - 45)  # 3.5mm jack 45mm from bottom
kenwood_z = ptt_z
for jack_dia, y_off in [(8.0, 0), (6.0, -KENWOOD_SPACING)]:
    jack = Pos(-WIDTH / 2, kenwood_y_top + y_off, kenwood_z) * Rot(0, 90, 0) * Cylinder(
        radius=jack_dia / 2, height=WALL * 3
    )
    bottom = bottom - jack

# USB-C hole through right wall (positive X)
USBC_W = 10   # along Y
USBC_H = 5    # along Z
usbc_top_z = floor_z + PERF_POST_HEIGHT + 5        # upper Z edge — 5mm above perfboard posts
usbc_center_z = usbc_top_z - USBC_H / 2
perf_top_post_y = perf_center_y + PERF_L / 2 - PERF_HOLE_FROM_TB
usbc_base_y = perf_top_post_y - 22                # lower Y edge, 22mm below top perfboard post
usbc_center_y = usbc_base_y + USBC_W / 2
usbc_hole = Pos(WIDTH / 2, usbc_center_y, usbc_center_z) * Box(
    WALL * 3, USBC_W, USBC_H  # oversized in X to cut clean through
)
bottom = bottom - usbc_hole

# Screen hole through floor (negative Z face), 33x19mm
SCREEN_W = 33   # along X
SCREEN_H = 19   # along Y
perf_left_post_x = perf_center_x - PERF_W / 2 + PERF_HOLE_FROM_LR
screen_center_x = perf_left_post_x + 37.5
screen_center_y = usbc_center_y  # centered on USB-C hole
screen_hole = Pos(screen_center_x, screen_center_y, -HEIGHT / 2) * Box(
    SCREEN_W, SCREEN_H, WALL * 3  # oversized in Z to cut clean through
)
bottom = bottom - screen_hole

# Speaker hole through floor (negative Z face), 28x28mm
SPEAKER_W = 30    # X axis (side with ears)
SPEAKER_L = 33    # Y axis
PA_BOARD_W = 26
inner_left = -WIDTH / 2 + WALL
speaker_center_x = inner_left + PA_BOARD_W + (WIDTH - 2 * WALL - PA_BOARD_W) / 2
speaker_center_y = LENGTH / 2 - 32 - SPEAKER_L / 2  # 32mm from top (shifted 20mm down)
speaker_hole = Pos(speaker_center_x, speaker_center_y, -HEIGHT / 2) * Box(
    SPEAKER_W, SPEAKER_L, WALL * 3
)
bottom = bottom - speaker_hole

# Speaker screw holes, 36mm apart, centered on speaker
for sx in [-18, 18]:
    screw = Pos(speaker_center_x + sx, speaker_center_y, -HEIGHT / 2) * Cylinder(
        radius=AMP_POST_ID / 2, height=WALL * 3
    )
    bottom = bottom - screw

# Mic hole through floor, 53mm below top perfboard post, 4mm right of left post
MIC_DIA = 10
mic_x = 0  # centered horizontally
mic_y = perf_top_post_y - 53
mic_hole = Pos(mic_x, mic_y, -HEIGHT / 2) * Cylinder(
    radius=MIC_DIA / 2, height=WALL * 3
)
bottom = bottom - mic_hole

# Lid screw posts — 3 posts from floor to split plane, triangle layout
LID_POST_HEIGHT = split_z - floor_z  # full height to split plane
LID_CLEARANCE_DIA = 2.4              # clearance hole in lid for M2 screw

lid_post_inset = WALL + AMP_POST_OD / 2  # post center inset from outer wall
lid_post_locs = [
    (+(WIDTH / 2 - lid_post_inset), +(LENGTH / 2 - lid_post_inset)),   # top-right (by speaker)
    (+(WIDTH / 2 - lid_post_inset), -(LENGTH / 2 - lid_post_inset)),   # bottom-right (by mic)
    (-(WIDTH / 2 - lid_post_inset), -(LENGTH / 2 - lid_post_inset)),   # bottom-left (other side of mic)
]

for px, py in lid_post_locs:
    cz = floor_z + (LID_POST_HEIGHT - OVERLAP) / 2
    post = Pos(px, py, cz) * Cylinder(radius=AMP_POST_OD / 2, height=LID_POST_HEIGHT + OVERLAP)
    hole = Pos(px, py, cz) * Cylinder(radius=AMP_POST_ID / 2, height=LID_POST_HEIGHT + 1)
    bottom = bottom + post - hole

# Clearance holes + countersinks through lid for flat-head M2 screws
CSINK_DIA = 4.0  # M2 flat-head diameter
csink_depth = (CSINK_DIA - LID_CLEARANCE_DIA) / 2  # 90° cone depth
lid_hole_z = split_z + LID_HEIGHT / 2
lid_top_z = HEIGHT / 2
for px, py in lid_post_locs:
    hole = Pos(px, py, lid_hole_z) * Cylinder(radius=LID_CLEARANCE_DIA / 2, height=LID_HEIGHT + 1)
    csink = Pos(px, py, lid_top_z - csink_depth / 2) * Cone(
        bottom_radius=LID_CLEARANCE_DIA / 2, top_radius=CSINK_DIA / 2, height=csink_depth
    )
    lid = lid - hole - csink

# Lid corner guides — tabs extending from lid into case for alignment
GUIDE_LEN = 15       # mm along edge
GUIDE_DEPTH = 2.5    # mm extending below split into case body
GUIDE_THICK = 1.5    # mm wall thickness
GUIDE_GAP = 0.3      # mm print clearance from case inner walls

inner_hx = WIDTH / 2 - WALL - GUIDE_GAP   # clearance from case inner walls
inner_hy = LENGTH / 2 - WALL - GUIDE_GAP
lid_inner_z = HEIGHT / 2 - WALL           # inside ceiling of lid
LID_OVERLAP = 1.0                         # mm past lid ceiling for clean boolean union
guide_total = (lid_inner_z - split_z) + GUIDE_DEPTH + LID_OVERLAP
guide_z = split_z + guide_total / 2 - GUIDE_DEPTH  # top extends into lid floor, bottom protrudes into case

guides = None
for sx, sy in [(+1, +1), (+1, -1), (-1, +1), (-1, -1)]:
    # L-bracket at each corner: one tab along X-wall, one along Y-wall
    # Tab along X-wall (constrains Y)
    gx = sx * (inner_hx - GUIDE_THICK / 2)
    corner_inset = FILLET_R + 10  # clear screw posts in corners
    gy = sy * (inner_hy - GUIDE_LEN / 2 - corner_inset)
    tab_x = Pos(gx, gy, guide_z) * Box(GUIDE_THICK, GUIDE_LEN, guide_total)
    # Tab along Y-wall (constrains X)
    gx2 = sx * (inner_hx - GUIDE_LEN / 2 - corner_inset)
    gy2 = sy * (inner_hy - GUIDE_THICK / 2)
    tab_y = Pos(gx2, gy2, guide_z) * Box(GUIDE_LEN, GUIDE_THICK, guide_total)
    # Chamfer bottom edges of each tab individually before combining
    GUIDE_CHAMFER = 0.5
    guide_bottom_z = guide_z - guide_total / 2
    for tab in [tab_x, tab_y]:
        bottom_edges = [e for e in tab.edges() if abs(e.center().Z - guide_bottom_z) < 0.1]
        if bottom_edges:
            tab = chamfer(bottom_edges, length=GUIDE_CHAMFER)
        guides = tab if guides is None else (guides + tab)

lid = lid + guides

# Move both onto the bed (Z=0) and place lid next to bottom
bottom = Pos(0, 0, -bottom.bounding_box().min.Z) * bottom
lid = Rot(180, 0, 0) * lid  # flip so flat top is on bed
lid = Pos(WIDTH + 5, 0, -lid.bounding_box().min.Z) * lid

# Combine into single print plate
plate = Compound(children=[bottom, lid])

# Export
export_step(plate, str(OUT / "case.step"))
export_stl(plate, str(OUT / "case.stl"))
print(f"Exported case: {WIDTH}x{LENGTH}x{HEIGHT}mm, lid={LID_HEIGHT}mm, wall={WALL}mm")

# CQ-editor preview
if "show_object" in dir():
    import cadquery as cq
    show_object(cq.Shape.cast(bottom.wrapped), name="bottom")
    show_object(cq.Shape.cast(lid.wrapped), name="lid")
