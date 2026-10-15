# Verify magnet pockets, assembled parts and head fit of a split wearable (Blender, run in Text Editor
# or through MCP). All parts must share one mesh frame (the body's local frame); display offsets on the
# objects are ignored because BVHs are built from raw mesh coordinates.
#
# Edit the names below, run, read the printed report.
import bpy, bmesh, math, re
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

BODY = 'Re375_corpo'
PAIRS = [                                   # (cutter object with one cylinder per pocket, part A, part B, magnet thickness)
    ('C375_sedi_linguette_v2', 'Re375_corpo', 'Re375_pannello', 3.0),
    ('C375_sedi_occhi', 'Re375_corpo', 'Re375_tappi_occhi', 2.0),
]
ASSEMBLED = ['Re375_pannello', 'Re375_tappi_occhi', 'Re375_corona']     # checked against BODY
ACCESSORY = 'Occhiali_375_stanghette_corte'   # glasses with arms cut to length, in the body frame (or None)
HEAD = 'Testa_prova'                          # scanned head object (world space) or None
HEAD_EYE_LOCAL = Vector((0, 0.2984, 0.0984))  # eye midpoint in the scan's local frame
KING_EYE = Vector((0, -105.1, 1.5))           # wearable's eye centre, body frame
HEAD_GRID = [(b, dz) for b in (40, 44, 48, 52) for dz in (-4, -8, -12)]


def raw_bvh(name):
    me = bpy.data.objects[name].data
    return BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [p.vertices[:] for p in me.polygons])


def inside(bv, p):
    n = 0; q = Vector(p); d = Vector((0.577, 0.578, 0.577))
    for _ in range(200):
        r = bv.ray_cast(q, d, 1e5)
        if r[0] is None: break
        n += 1; q = r[0] + d * 1e-4
    return n % 2 == 1


def cylinders(name):
    """Split the cutter into cylinders: (centre, axis, length, radius)."""
    bm = bmesh.new(); bm.from_mesh(bpy.data.objects[name].data); bm.verts.ensure_lookup_table()
    seen = set(); out = []
    for v in bm.verts:
        if v.index in seen: continue
        st = [v]; c = []
        while st:
            x = st.pop()
            if x.index in seen: continue
            seen.add(x.index); c.append(np.array(x.co)); st.extend(e.other_vert(x) for e in x.link_edges)
        c = np.array(c); cen = c.mean(0); _, _, vt = np.linalg.svd(c - cen)
        spans = [np.ptp((c - cen) @ vt[i]) for i in range(3)]
        diffs = [abs(spans[i] - spans[(i + 1) % 3]) + abs(spans[i] - spans[(i + 2) % 3]) for i in range(3)]
        ai = int(np.argmax(diffs))
        out.append((Vector(cen), Vector(vt[ai]), spans[ai], np.median([spans[i] for i in range(3) if i != ai]) / 2))
    bm.free(); return out


def profile(bv, cen, a, L, R):
    """# = material on the axis, o = full wall (12/12), a..l = partial wall, . = air; one char per 0.5 mm."""
    perp = a.orthogonal().normalized(); perp2 = a.cross(perp); line = ''
    for t in np.arange(-L / 2 - 3.0, L / 2 + 3.1, 0.5):     # +-3 mm: pockets deepened after cutting
        p = cen + a * t
        ring = sum(inside(bv, p + (perp * math.cos(g) + perp2 * math.sin(g)) * (R + 0.35))
                   for g in np.linspace(0, 2 * math.pi, 12, endpoint=False))
        line += '#' if inside(bv, p) else ('o' if ring == 12 else (chr(ord('a') + ring - 1) if ring else '.'))
    return line


def pockets():
    print("== pocket profiles (# bottom, o full wall, a-k partial, . air) ==")
    for cutter, A, B, thick in PAIRS:
        bvs = {A: raw_bvh(A), B: raw_bvh(B)}
        for k, (cen, a, L, R) in enumerate(cylinders(cutter)):
            for part, bv in bvs.items():
                line = profile(bv, cen, a, L, R)
                # longest run of full wall, allowing single 11/12 points (k) inside the run
                full = max((len(s) for s in re.findall(r'[ok]*o[ok]*', line)), default=0) * 0.5
                flag = 'OK' if full >= thick else 'TOO SHALLOW / TILTED'
                print(f"{cutter} #{k+1} {part:20s} {line}  full wall {full:.1f} mm  {flag}")


def assembled():
    print("== assembled interference against", BODY, "==")
    bvB = raw_bvh(BODY)
    for n in ASSEMBLED:
        bv = raw_bvh(n); me = bpy.data.objects[n].data
        idx = np.random.default_rng(0).choice(len(me.vertices), min(6000, len(me.vertices)), replace=False)
        d = min(bvB.find_nearest(me.vertices[int(i)].co)[3] for i in idx)
        print(f"{n}: overlapping face pairs {len(bvB.overlap(bv))}, min distance {d:.2f} mm")
    if ACCESSORY and ACCESSORY in bpy.data.objects:
        bv = raw_bvh(ACCESSORY); me = bpy.data.objects[ACCESSORY].data
        d = min(bvB.find_nearest(v.co)[3] for v in me.vertices)
        print(f"{ACCESSORY}: overlapping face pairs {len(bvB.overlap(bv))}, min distance {d:.2f} mm")


def head_fit():
    if not HEAD or HEAD not in bpy.data.objects: return
    print("== head fit (eyes back / down from the eye centre) ==")
    body = bpy.data.objects[BODY]; Minv = body.matrix_world.inverted(); h = bpy.data.objects[HEAD]
    parts = [BODY] + [n for n in ASSEMBLED if n in bpy.data.objects]
    bvs = [raw_bvh(n) for n in parts]
    for back, dz in HEAD_GRID:
        h.location = (0, 0, 0); bpy.context.view_layer.update()
        target = body.matrix_world @ (KING_EYE + Vector((0, back, dz)))
        h.location = target - (h.matrix_world @ HEAD_EYE_LOCAL); bpy.context.view_layer.update()
        V = [Minv @ (h.matrix_world @ v.co) for v in h.data.vertices]
        V = [p for p in V if p.z > KING_EYE.z - 130][::2]
        pen = 0; mn = 1e9
        for bv in bvs:
            for p in V:
                r = bv.find_nearest(p)
                if r[0] is None: continue
                mn = min(mn, r[3])
                if r[3] < 15 and inside(bv, p): pen += 1
        print(f"back {back} mm, down {-dz} mm: vertices inside {pen}, min clearance {mn:.1f} mm")


pockets(); assembled(); head_fit()
