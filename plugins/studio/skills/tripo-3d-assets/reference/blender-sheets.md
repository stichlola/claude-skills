# Splitting a Tripo sheet into pieces (Blender, bmesh)

Run headless: `blender -b --factory-startup --python-exit-code 1 -P split.py -- <args>`.

1. Import the GLB, join its meshes, apply transforms.
2. Measure on Tripo's front view (`rendered_image_url`, or a Blender ortho render) the centre of each
   piece in the sheet's own coordinates → `CENTRES = {"piece": ((y, z), ...)}`. Tripo gives the sheet
   with its front towards +x, laid along y, z up.
3. Split: weld, find shells, give each shell to the nearest centre.

```python
import bmesh
from mathutils import Vector

def islands(bm):
    """The faces of each loose shell (vertices welded by position first: Tripo leaves them split)."""
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bm.faces.index_update(); bm.faces.ensure_lookup_table()
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, group = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop(); group.append(g)
            for v in g.verts:
                for h in v.link_faces:
                    if h.index not in seen:
                        seen.add(h.index); stack.append(h)
        out.append(group)
    return out

def split_sheet(ob, centres):
    """One bmesh per piece: every shell to the piece whose middle is nearest its own."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    groups = {k: set() for k in centres}
    for isl in islands(bm):
        area = sum(f.calc_area() for f in isl) or 1e-9
        c = sum((f.calc_center_median() * f.calc_area() for f in isl), Vector()) / area
        k = min(centres, key=lambda k: (c.y - centres[k][0][0]) ** 2 + (c.z - centres[k][0][1]) ** 2)
        groups[k].update(f.index for f in isl)
    out = {}
    for k in centres:
        part = bm.copy(); part.faces.index_update()
        bmesh.ops.delete(part, geom=[f for f in part.faces if f.index not in groups[k]], context="FACES")
        bmesh.ops.delete(part, geom=[v for v in part.verts if not v.link_faces], context="VERTS")
        out[k] = part
    bm.free()
    return out
```

4. Cuts (tree crown from trunk, a stand off the bottom): `bmesh.ops.bisect_plane(..., clear_inner=True)`
   then close the hole with `bmesh.ops.triangle_fill` on the cut edges, flip the new faces to face out
   and set their UVs to the average UV of the ring (so the cap takes the colour around it).
   Tripo meshes are thin shells: where a cut leaves no closed ring, add a closed box inside ("core").
5. Place: matrix = scale(true size / measured size) @ rotate(front to the game's front) @
   translate(-foot centre). Clear custom normals, then `shade_smooth_by_angle(50°)`.
6. Material: one per sheet, Tripo's colour map scaled to 1024, roughness 0.8 (keep the raw PBR file for
   Unreal).
7. Parent each piece's mesh to an empty named `<prefix>_<piece>`, export selected as GLB (`export_yup`,
   `export_apply`, `export_image_format="WEBP"`), then `gltfpack -i plain.glb -o kit.glb -cc -kn -km -ke -vp 12`.
8. Render a contact sheet (all pieces in a row, ortho camera from the game's angle, a hero-sized figure
   for scale) and look at it before wiring anything into the game.
