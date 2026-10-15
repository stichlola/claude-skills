"""Find (and with --fix, close) the holes in and around Haven City.

    blender -b world_edit1.blend -P tools/blender/haven_holes.py -- REPORT.png [--fix]

On a CELL grid over the districts and MARGIN around them, a ray straight down from the sky finds
what the player would stand on or see from above:
- HOLE: inside the city (CITY_RADIUS from any district piece) only water or nothing below the
  street, outside the port's bay (BAY, the one water the city keeps);
- VOID: nothing at all and no sea there either (the game's seas cover HAVEN_SEA only);
- DROP: a city cell whose floor is over STEP higher than a neighbor that is water or void (an
  open edge: the street ends in the air);
the rest is fine (city floor, terrain, the bay, the open sea).
REPORT.png is a top view (north up): fine = grey by height, HOLE = red, VOID = magenta,
DROP = yellow, bay and sea = blue. With --fix, "HavenPatch" (Custom collection, parented to
HavenCity) gets a street-level slab over every HOLE/VOID cell and a skirt wall down to the
water under every DROP edge, and the file is saved.
"""

import math
import struct
import sys
import zlib
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
REPORT = Path(args[0]) if args else Path("haven_holes.png")
FIX = "--fix" in args
CELL = 6.0
MARGIN = 300.0
CITY_RADIUS = 18.0
STEP = 6.0
DISTRICTS = ["ctyport", "ctysluma", "ctyslumb", "ctyslumc", "ctyinda", "ctyindb", "ctyfarma", "ctyfarmb", "ctygenb"]
# tools/blender/haven_terrain.py: the port's bay, the only water left inside the city.
BAY = (1100.0, 1900.0, 4350.0, 5600.0)

root = bpy.data.objects["HavenCity"]
sea = root.location.z  # Haven's sea (GOAL 0 m) in the world
street = sea + 6.0
depsgraph = bpy.context.evaluated_depsgraph_get()

city = set()
for level in DISTRICTS:
    city |= {o for o in bpy.data.objects["cty_" + level].children_recursive if o.type == "MESH"}
skip_collections = {"Kit", "Kit erba", "Kit erba alta", "Kit alberi", "Kit palme", "Kit latifoglie", "Kit massi",
                    "Kit guglie", "Kit case", "Kit rocce"}
meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name not in ("Mare", "HavenPatch")
          and not o.name.startswith(("Sparsi", "_look"))
          and not ({c.name for c in o.users_collection} & skip_collections)]
verts, polys, owner = [], [], []
for obj in meshes:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    base = len(verts)
    m = obj.matrix_world
    verts += [m @ v.co for v in mesh.vertices]
    for p in mesh.polygons:
        polys.append(tuple(base + i for i in p.vertices))
        owner.append(obj in city)
    evaluated.to_mesh_clear()
tree = BVHTree.FromPolygons(verts, polys)
print(f"haven_holes: {len(meshes)} meshes, {len(polys)} faces")

pts = [o.matrix_world @ Vector(c) for o in city for c in o.bound_box]
x0 = min(p.x for p in pts) - MARGIN
x1 = max(p.x for p in pts) + MARGIN
y0 = min(p.y for p in pts) - MARGIN
y1 = max(p.y for p in pts) + MARGIN
W, H = int((x1 - x0) // CELL) + 1, int((y1 - y0) // CELL) + 1
top = np.full((H, W), np.nan)
is_city = np.zeros((H, W), bool)
down = Vector((0.0, 0.0, -1.0))
for r in range(H):
    y = y0 + (r + 0.5) * CELL
    for c in range(W):
        x = x0 + (c + 0.5) * CELL
        loc, _n, index, _d = tree.ray_cast(Vector((x, y, 4000.0)), down)
        if loc is not None:
            top[r, c] = loc.z
            is_city[r, c] = owner[index]

# Cells near district geometry (dilated) count as "inside the city".
near = is_city.copy()
steps = int(CITY_RADIUS // CELL)
for _ in range(steps):
    grown = near.copy()
    grown[1:] |= near[:-1]
    grown[:-1] |= near[1:]
    grown[:, 1:] |= near[:, :-1]
    grown[:, :-1] |= near[:, 1:]
    near = grown
xs = x0 + (np.arange(W) + 0.5) * CELL
ys = y0 + (np.arange(H) + 0.5) * CELL
bay = (xs[None, :] >= BAY[0]) & (xs[None, :] <= BAY[1]) & (ys[:, None] >= BAY[2]) & (ys[:, None] <= BAY[3])
wet = np.isnan(top) | (top < sea - 0.3)
# Water that reaches the edge of the scan is open sea (the port opens on it): allowed. Every
# other wet patch is shut in by the city: a hole, whatever its size.
open_water = np.zeros((H, W), bool)
stack = [(r, c) for r in range(H) for c in (0, W - 1) if wet[r, c]] +         [(r, c) for c in range(W) for r in (0, H - 1) if wet[r, c]]
for r, c in stack:
    open_water[r, c] = True
while stack:
    r, c = stack.pop()
    for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
        if 0 <= rr < H and 0 <= cc < W and wet[rr, cc] and not open_water[rr, cc]:
            open_water[rr, cc] = True
            stack.append((rr, cc))
# The port keeps its water: wet cells inside the port district's box.
port = [o.matrix_world @ Vector(c) for o in bpy.data.objects["cty_ctyport"].children_recursive
        if o.type == "MESH" for c in o.bound_box]
px0, px1 = min(p.x for p in port), max(p.x for p in port)
py0, py1 = min(p.y for p in port), max(p.y for p in port)
in_port = (xs[None, :] >= px0) & (xs[None, :] <= px1) & (ys[:, None] >= py0) & (ys[:, None] <= py1)
open_water |= wet & in_port
bay = bay | open_water
hole = wet & ~open_water
void = np.zeros((H, W), bool)
dry = ~wet
drop = np.zeros((H, W), bool)
for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    neighbor_wet = np.zeros((H, W), bool)
    neighbor_top = np.full((H, W), np.nan)
    rs = slice(max(dr, 0), H + min(dr, 0))
    rd = slice(max(-dr, 0), H + min(-dr, 0))
    cs = slice(max(dc, 0), W + min(dc, 0))
    cd = slice(max(-dc, 0), W + min(-dc, 0))
    neighbor_wet[rs, cs] = (wet & ~bay)[rd, cd]
    drop |= dry & is_city & neighbor_wet & (np.nan_to_num(top, nan=-1e9) > sea + STEP)
print(f"haven_holes: {W} x {H} cells of {CELL} m: {int(hole.sum())} hole, {int(void.sum())} void, "
      f"{int(drop.sum())} drop cells")

# Report image (north up).
lo, hi = np.nanpercentile(top, 2), np.nanpercentile(top, 98)
grey = np.clip((np.nan_to_num(top, nan=lo) - lo) / max(1.0, hi - lo), 0, 1) * 170 + 60
img = np.stack([grey, grey, grey], -1).astype(np.uint8)
img[wet] = (40, 90, 160)
img[hole] = (230, 30, 30)
img[void] = (230, 30, 230)
img[drop] = (250, 220, 20)
img = img[::-1]
raw = b"".join(b"\0" + row.tobytes() for row in img)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
                   + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
print(f"haven_holes: report {REPORT}")

if FIX:
    material = bpy.data.materials.get("faraway-street")
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    # Slabs: the floor height of the city cells around each hole (or the street), 0.2 m above.
    fill = hole | void
    floor = np.where(dry & is_city, top, np.nan)
    level = np.full((H, W), street)
    for r, c in zip(*np.nonzero(fill)):
        around = floor[max(r - 3, 0):r + 4, max(c - 3, 0):c + 4]
        if np.isfinite(around).any():
            level[r, c] = float(np.nanmedian(around))
    for r, c in zip(*np.nonzero(fill)):
        x, y, z = x0 + c * CELL, y0 + r * CELL, level[r, c] + 0.2
        face = bm.faces.new([bm.verts.new((x, y, z)), bm.verts.new((x + CELL, y, z)),
                             bm.verts.new((x + CELL, y + CELL, z)), bm.verts.new((x, y + CELL, z))])
        for loop, (u, v) in zip(face.loops, ((x, y), (x + CELL, y), (x + CELL, y + CELL), (x, y + CELL))):
            loop[uv].uv = (u / 6.0, v / 6.0)
    # Skirts under the open edges, down to below the sea.
    for r, c in zip(*np.nonzero(drop)):
        x, y, z = x0 + c * CELL, y0 + r * CELL, top[r, c]
        for dr, dc, a, b in ((1, 0, (0, 1), (1, 1)), (-1, 0, (0, 0), (1, 0)), (0, 1, (1, 0), (1, 1)), (0, -1, (0, 0), (0, 1))):
            rr, cc = r + dr, c + dc
            if not (0 <= rr < H and 0 <= cc < W) or not (wet[rr, cc] and not bay[rr, cc]):
                continue
            pa = (x + a[0] * CELL, y + a[1] * CELL)
            pb = (x + b[0] * CELL, y + b[1] * CELL)
            face = bm.faces.new([bm.verts.new((pa[0], pa[1], sea - 3.0)), bm.verts.new((pb[0], pb[1], sea - 3.0)),
                                 bm.verts.new((pb[0], pb[1], z)), bm.verts.new((pa[0], pa[1], z))])
            for loop, coord in zip(face.loops, ((0, 0), (1, 0), (1, (z - sea + 3) / 6), (0, (z - sea + 3) / 6))):
                loop[uv].uv = coord
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    old = bpy.data.objects.get("HavenPatch")
    if old:
        data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    mesh = bpy.data.meshes.new("HavenPatch")
    bm.to_mesh(mesh)
    bm.free()
    if material:
        mesh.materials.append(material)
    obj = bpy.data.objects.new("HavenPatch", mesh)
    bpy.data.collections["Custom"].objects.link(obj)
    obj.parent = root
    obj.matrix_parent_inverse = root.matrix_world.inverted()
    bpy.ops.wm.save_mainfile()
    print(f"haven_holes: HavenPatch {len(mesh.polygons)} faces, saved")
