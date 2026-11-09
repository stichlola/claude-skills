# mesh-hygiene: check and clean meshes before export or hand-off: duplicate vertices/edges, degenerate (zero-thickness) triangles,
# non-manifold edges, tiny loose islands. Run in a background Blender on a COPY of the file:
#   blender -b copy.blend --python mesh_clean.py -- <out_dir> [object names...]     (no names = every visible mesh)
#   add --check to only report.
# Prints, per object: duplicates, zero-area faces, flat faces (height < 1 micron), non-manifold edges, loose islands,
# volume, before and after. Writes <out_dir>/<name>.stl and <out_dir>/cleaned.blend with the cleaned objects.
import bpy, bmesh, sys, os, numpy as np
A = sys.argv[sys.argv.index('--')+1:]
CHECK = '--check' in A; A = [a for a in A if a != '--check']
OUT, NAMES = A[0], A[1:]
os.makedirs(OUT, exist_ok=True)
obs = [bpy.data.objects[n] for n in NAMES] if NAMES else [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get()]
for o in obs:   # objects from a previous cleaned.blend have only a fake user: link them so they can be selected for export
    if o.name not in bpy.context.view_layer.objects: bpy.context.scene.collection.objects.link(o)

def report(bm):
    bm.verts.index_update()
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    a = np.array([f.calc_area() for f in bm.faces])
    h = np.array([2*f.calc_area()/max(max(e.calc_length() for e in f.edges), 1e-12) for f in bm.faces])
    co = np.array([v.co[:] for v in bm.verts]); dup = len(co)-len(np.unique(np.round(co/0.001).astype(np.int64), axis=0))
    ek = {tuple(sorted((e.verts[0].index, e.verts[1].index))) for e in bm.edges}; dup_e = len(bm.edges)-len(ek)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    return dict(faces=len(a), dup_verts=dup, dup_edges=dup_e, area0=int((a < 1e-8).sum()), flat=int((h < 1e-3).sum()), non_manifold=nm, volume_cm3=round(bm.calc_volume()/1000, 2))

def clean(bm):
    for _ in range(3):
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.002)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        bad = [f for f in bm.faces if 2*f.calc_area()/max(max(e.calc_length() for e in f.edges), 1e-12) < 1e-3]
        if not bad: break
        bmesh.ops.collapse(bm, edges=list({min(f.edges, key=lambda e: e.calc_length()) for f in bad}))
    for _ in range(30):  # non-manifold: remove two rings of faces around each bad edge, split bowties, fill, repeat
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        nm = [e for e in bm.edges if not e.is_manifold]
        if not nm: break
        fs = {f for e in nm for v in e.verts for f in v.link_faces}; fs |= {g for f in list(fs) for v in f.verts for g in v.link_faces}
        bmesh.ops.delete(bm, geom=list(fs), context='FACES_ONLY')
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bmesh.ops.split_edges(bm, edges=[e for e in bm.edges if not e.is_manifold and not e.is_boundary])
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    # tiny loose islands (booleans leave 4-10 vertex specks)
    # (indices refreshed first and islands deleted only after the walk: stale indices or deleting while walking crash on big meshes)
    bm.verts.index_update(); seen = set(); specks = []
    for v0 in bm.verts:
        if v0.index in seen: continue
        st, isl = [v0], []; seen.add(v0.index)
        while st:
            v = st.pop(); isl.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen: seen.add(w.index); st.append(w)
        if len(isl) < 50: specks += isl
    if specks: bmesh.ops.delete(bm, geom=specks, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

done = []
for o in obs:
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    print('PRIMA', o.name, report(bm.copy()), flush=True)
    if CHECK: bm.free(); continue
    clean(bm); bm.verts.index_update(); r = report(bm.copy()); print('DOPO ', o.name, r, flush=True)
    bm.transform(o.matrix_world.inverted()); bm.to_mesh(o.data); bm.free(); o.data.update(); done.append(o)
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.wm.stl_export(filepath=os.path.join(OUT, o.name+'.stl'), export_selected_objects=True, global_scale=1.0)
if done: bpy.data.libraries.write(os.path.join(OUT, 'cleaned.blend'), set(done), fake_user=True)
print('FINE', flush=True)
