# Engraved D8 for 3D printing (Blender 4.2+, verified in 5.1). Units: millimetres.
# Run in Blender's Text Editor. Creates: D8_bevel (clean bevelled die), D8_texts/* (text cutters, one per
# face, 0.3 mm outside to DEPTH inside), D8_texts_joined, D8_masks/* (paint stencils: plate + tall text),
# and, if ENGRAVE, D8_engraved (SDF difference).
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

EDGE_MM   = 19.6            # D8 edge length (27.7 mm vertex to vertex)
BEVEL_MM  = 0.6
DEPTH     = 0.5             # engraving depth
OUTSIDE   = 0.3             # how far the cutters stick out of the face
MARGIN    = 1.5             # min distance text <-> face edge
FONT_PATH = r"C:\Windows\Fonts\timesbd.ttf"
SPACING   = 1.06            # letter spacing; lower -> glyphs touch -> self-intersecting cutters
ENGRAVE   = False           # True: also build D8_engraved by SDF
VOXEL     = 0.07
LOCATION  = Vector((0.0, 0.0, 0.0))
# face key = sign of the face normal (x, y, z); upper faces z=+1
TEXTS = {
    (+1, -1, +1): "FALLO!",          (+1, -1, -1): "CAMBIA\nDOMANDA",
    (+1, +1, +1): "FREGA-\nTENE",    (+1, +1, -1): "DORMICI\nSU",
    (-1, +1, +1): "CHIAMA\nLE AMICHE", (-1, +1, -1): "PUOI\nSBAGLIARE",
    (-1, -1, +1): "LO SAI\nGIÀ.",    (-1, -1, -1): "ABITA\nIL VUOTO",
}

scn = bpy.context.scene
a = EDGE_MM / math.sqrt(2)            # centre-to-vertex
zc = a                                # die stands on its bottom vertex at z=0
H = EDGE_MM * math.sqrt(3) / 2        # triangle height
YC = 0.29 * H                         # text block centre, from the long side

def coll(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in [x.name for x in scn.collection.children]:
        scn.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o)
    return c

def replace(name, me, c=None):
    old = bpy.data.objects.get(name)
    if old is not None:
        m = old.data; bpy.data.objects.remove(old)
        if m and m.users == 0: bpy.data.meshes.remove(m)
    o = bpy.data.objects.new(name, me); (c or scn.collection).objects.link(o); return o

# ---- clean die + bevel
V = {'+x': (a, 0, zc), '-x': (-a, 0, zc), '+y': (0, a, zc), '-y': (0, -a, zc), '+z': (0, 0, zc + a), '-z': (0, 0, zc - a)}
F = [('+x', '+y', '+z'), ('+y', '-x', '+z'), ('-x', '-y', '+z'), ('-y', '+x', '+z'),
     ('+y', '+x', '-z'), ('-x', '+y', '-z'), ('-y', '-x', '-z'), ('+x', '-y', '-z')]
keys = list(V)
me = bpy.data.meshes.new('D8_bevel'); me.from_pydata([V[k] for k in keys], [], [tuple(keys.index(k) for k in f) for f in F]); me.update()
bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=BEVEL_MM, segments=4, profile=0.5, affect='EDGES', clamp_overlap=True)
bm.to_mesh(me); bm.free()
die = replace('D8_bevel', me); die.location = LOCATION

# ---- texts
font = bpy.data.fonts.load(FONT_PATH, check_existing=True)
tc = coll('D8_texts'); mc = coll('D8_masks')
def width_at(y): return EDGE_MM * (1 - y / H)
cutters = []
for key, txt in TEXTS.items():
    n = Vector(key).normalized(); up = (Vector((0, 0, 1)) - n * n.z).normalized(); right = up.cross(n).normalized()
    centroid = Vector((0, 0, zc)) + n * (a / math.sqrt(3))
    shift = -(1 if n.z > 0 else -1) * (H / 3 - YC)
    safe = ''.join(ch if ch.isalnum() else '_' for ch in txt.replace('\n', ' '))
    cu = bpy.data.curves.new('T_' + safe, 'FONT'); cu.body = txt; cu.font = font
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.size = 1.0; cu.space_line = 0.92; cu.space_character = SPACING
    cu.extrude = (DEPTH + OUTSIDE) / 2; cu.fill_mode = 'BOTH'
    ob = bpy.data.objects.new('T_' + safe, cu); tc.objects.link(ob)
    M = Matrix(((right.x, up.x, n.x, 0), (right.y, up.y, n.y, 0), (right.z, up.z, n.z, 0), (0, 0, 0, 1)))
    ob.matrix_world = Matrix.Translation(LOCATION + centroid + up * shift + n * ((OUTSIDE - DEPTH) / 2)) @ M
    bpy.context.view_layer.update()
    bb = [Vector(v) for v in ob.bound_box]; w = max(v.x for v in bb) - min(v.x for v in bb); h = max(v.y for v in bb) - min(v.y for v in bb)
    size = 0.6
    for s in np.arange(0.6, 12.0, 0.05):
        if w * s + 2 * MARGIN <= width_at(YC + h * s / 2) and h * s <= 0.55 * H: size = s
    cu.size = size; bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.convert(target='MESH'); ob.name = 'M_' + safe
    bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    tree = BVHTree.FromBMesh(bm); overlaps = len(tree.overlap(tree)); bm.to_mesh(ob.data); bm.free()
    print(f"{txt!r}: size {size:.2f}, self-overlaps {overlaps}" + ("  <- raise SPACING" if overlaps else ""))
    cutters.append(ob)
    # paint mask: plate on the face + tall copy of the text
    def face_key(f):
        c = sum((Vector(V[k]) for k in f), Vector()) / 3 - Vector((0, 0, zc))
        return (int(math.copysign(1, c.x)), int(math.copysign(1, c.y)), int(math.copysign(1, c.z)))
    tri = [Vector(V[k]) for k in next(f for f in F if face_key(f) == key)]
    pts = [LOCATION + p + n * 0.05 for p in tri] + [LOCATION + p + n * 1.05 for p in tri]
    pm = bpy.data.meshes.new('MASK_' + safe); pm.from_pydata([tuple(p) for p in pts], [], [(0, 1, 2), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]); pm.update()
    bm = bmesh.new(); bm.from_mesh(pm); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(pm); bm.free()
    mc.objects.link(bpy.data.objects.new('MASK_' + safe, pm))
    tm = ob.data.copy(); tm.name = 'MASKTXT_' + safe; tm.transform(ob.matrix_world)
    c0 = LOCATION + centroid
    for v in tm.vertices:
        p = Vector(v.co); d = (p - c0).dot(n); d2 = -0.2 + (d + DEPTH) / (DEPTH + OUTSIDE) * 1.7; v.co = p + n * (d2 - d)
    mc.objects.link(bpy.data.objects.new('MASKTXT_' + safe, tm))

# ---- joined cutters (one object, world coordinates)
jm = bpy.data.meshes.new('D8_texts_joined'); bmj = bmesh.new()
for ob in cutters:
    t = ob.data.copy(); t.transform(ob.matrix_world); bmj.from_mesh(t); bpy.data.meshes.remove(t)
bmj.to_mesh(jm); bmj.free()
joined = replace('D8_texts_joined', jm, tc); joined.hide_set(True)

# ---- optional SDF engraving
if ENGRAVE:
    ng = bpy.data.node_groups.get('D8_engrave') or bpy.data.node_groups.new('D8_engrave', 'GeometryNodeTree')
    ng.is_modifier = True; ng.use_fake_user = True; ng.nodes.clear()
    for it in list(ng.interface.items_tree): ng.interface.remove(it)
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes.new; L = lambda x, o, y, i: ng.links.new(x.outputs[o], y.inputs[i])
    gi = N('NodeGroupInput'); go = N('NodeGroupOutput')
    s1 = N('GeometryNodeMeshToSDFGrid'); s1.inputs['Voxel Size'].default_value = VOXEL; s1.inputs['Band Width'].default_value = 4
    oi = N('GeometryNodeObjectInfo'); oi.inputs['Object'].default_value = joined; oi.transform_space = 'RELATIVE'
    s2 = N('GeometryNodeMeshToSDFGrid'); s2.inputs['Voxel Size'].default_value = VOXEL; s2.inputs['Band Width'].default_value = 4
    d = N('GeometryNodeSDFGridBoolean'); d.operation = 'DIFFERENCE'
    g = N('GeometryNodeGridToMesh'); g.inputs['Threshold'].default_value = 0.0
    L(gi, 'Geometry', s1, 'Mesh'); L(oi, 'Geometry', s2, 'Mesh'); L(s1, 'SDF Grid', d, 'Grid 1'); L(s2, 'SDF Grid', d, 'Grid 2'); L(d, 'Grid', g, 'Grid'); L(g, 'Mesh', go, 'Geometry')
    eng = replace('D8_engraved', die.data.copy()); eng.location = LOCATION
    md = eng.modifiers.new('engrave', 'NODES'); md.node_group = ng
    bpy.ops.object.select_all(action='DESELECT'); eng.select_set(True); bpy.context.view_layer.objects.active = eng
    bpy.ops.object.modifier_apply(modifier='engrave')
    print("D8_engraved faces:", len(eng.data.polygons))
print("done")
