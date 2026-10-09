---
name: blender-wearable-hollowing
description: Turn a solid sculpt (Tripo or any dense mesh) into a 3D-printable wearable shell in Blender - hollow it with Geometry Nodes SDF grids, open the bottom without touching the visible outline, extend hair or a collar, cut removable parts (eyes) with magnet pockets at real-world millimetres, verify fit with numbers, bake a real mesh for hand sculpting, render client previews. Includes the MCP-for-Blender pitfalls (empty Grid to Mesh, Object Info spaces, no re-evaluation after Python edits, call timeouts) and a full working build script. Use for mascot heads, helmets, masks, cosplay shells, any "make it hollow so a person fits inside" job, and whenever driving Blender 4.x/5.x through MCP with SDF or boolean nodes.
---

# Hollow wearables in Blender (Geometry Nodes SDF + MCP)

Lessons from a wearable king's head (crown, beard, removable magnetic eyes, 1 m Tripo model printed at
~50 cm) driven entirely through MCP for Blender in Blender 5.1. Everything below was verified there.

## Hard rules

- **Keep the sculpt's scale as the user gave it** (Tripo models are 1 m tall, normalised). Real-world
  features (magnet pockets, clearances, wall thickness) are converted with one `SCALE_CM` constant at the
  top of the script; say the assumed print height in the report, every time.
- **Never hand-build on the procedural object.** The modifier output is not sculptable (base mesh has 0
  verts). Bake a real mesh (`bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))`) and tell
  the user that hand edits on the bake are lost if the parameters change.
- **Verify with numbers, then look**: horizontal sections (list the y-walls at x=0 and x-walls at y=0
  for several z), bounding boxes, manifold check, "0 vertices inside the hole", signed volume. A
  screenshot alone missed a closed-off eye hole once.
- **Better too wide than too tight**: a shell the head doesn't fit is thrown away. Target at print scale:
  cavity ≥ 24 cm wide and ≥ 26 cm deep at eye level, bottom opening ≥ 20 × 24 cm (a head is ~16 wide,
  ~20 deep, chin-to-crown ~23). Report the opening and cavity in cm.
- Load **only what the task needs**; booleans on the whole 400k-face mesh are fine (~10 s) but every
  parameter tweak re-runs them, so give the modifier on/off switches (`Scava`, `Taglia occhi`).

## The pipeline (all inside one Geometry Nodes group, built by script)

```
head (closed copy) ─ Mesh to SDF Grid ─┐
extension solid ─ Mesh to SDF Grid ────┴ SDF Boolean UNION = A
A ─ SDF Grid Offset(−wall) ─ Grid to Mesh ─ Blur Attribute(position, N) ─ Set Position ─ Mesh to SDF = B'
shell = A − B'                                  (hollow, closed)
shell − bottom cutter SDF                       (open bottom)
Grid to Mesh (Threshold 0!) ─ Mesh Boolean DIFFERENCE [eye cutters, magnet pockets] = helmet
plugs = GridToMesh(shell ∩ box around eyes) ∩ plug solids − pockets   (small meshes → fast booleans)
Switch nodes: Scava / Taglia occhi / Output tappi
```

- Wall thickness 0.04 on a 1 m model (= 2 cm at 50 cm). Band Width 16 voxels at voxel 0.004 so the
  negative offset stays inside the narrow band.
- **Smoothing the cavity**: Blur Attribute on positions (100-150 iterations) removes hair bumps from the
  inside; it also shrinks concave areas (walls up to 2× thicker at the mouth), which is fine.
- **Voxel 0.004** ≈ 2 mm at 50 cm, 400k faces, 10-30 s. 0.003 doubles faces and fixes speckles on thin
  parts (crown band). Below 0.003 there is no more detail to recover if the input is itself a remesh.
- Helpers (cutters, extension, pockets) are plain meshes built with numpy/bmesh in a hidden collection
  and read through **Object Info**; the group is rebuilt by the script every run (`nodes.clear()`).

## Opening the bottom without changing the visible outline

- Original Tripo busts end in a **concave dish** that rises into the head (apex 17 cm up on a 1 m
  model). Cutting at the rim is not enough: the floor stays and closes the cavity. Measure it first
  (lowest down-facing vertices by radius) and make the cutter reach above the apex + wall.
- **Opening prism**: take the horizontal outline at a level just above the rim (polar bins around the
  outline's centre, 1440 bins, max radius per bin, gaps interpolated, low-pass filtered), shrink it by
  wall + 12 mm, extrude from above the dish apex down to −1. It removes only the hidden underside wall
  (under the chin, behind the beard); hair, beard and the outer neck line stay as they were.
- **A beard that hangs lower than the rim** must be spared: a heightfield cutter with a local dip under
  the beard footprint (an ellipse), never a flat plane, or the beard tip is sliced.
- Any closed solid you add (hair skirt) inside the beard footprint leaves fins or floors. Subtract a
  "notch" prism (beard footprint dilated 1.5 cm, below the beard's shoulder) from the skirt before the
  union, so the skirt simply doesn't exist where the beard is.

## Extending hair / a collar to cover the neck

Sample the outline at the level where the hair is fullest, start the skirt buried inside the hair
(ZTOP above the sample level), extrude down to below the cutter with a slight taper (0.93) and a tiny
sine noise; keep the outline's bumps (they read as vertical strands). Clamp the front with an ellipse
(smooth-min) so the skirt sits behind the beard, moving backwards as the beard narrows downwards.
A wavy bottom edge comes free from the cutter heightfield (bump term from the outline's high-pass).

## Removable parts with magnets (what the client accepted)

- A stepped plug with a flange and axial pockets was **rejected as unrealistic**. What works: a
  straight plug cut from the wall with a slight **cone (radius −1 mm per 10 mm depth, wider outside)** so
  it can't fall inward, 0.4 mm radial clearance, and **radial magnet pockets across the gap**: one
  cylinder per position, axis parallel to the surface, half its length in the plug and half in the wall,
  subtracted from both. Two per eye (top and bottom) → 4 magnets per eye. 8×3 mm neodymium discs, pocket
  Ø+0.5 mm, depth 3.4 mm per side.
- Pocket centre depth = max(local outer-surface recess + 1.5 mm + pocket radius, 12 mm); check what is
  left towards the cavity (≥ 1.5 mm) and print a per-pocket report.
- **Depth sign**: define the eye frame with the normal pointing INTO the head and call depth positive
  inside. With the outward normal the flange and step ended up floating in front of the face.
- Eye positions: ortho front render through a known camera (ortho_scale, resolution → pixel to metres)
  is the fastest way to read centres and sizes; tilt the ellipse ~8° (outer corner lower).
- Plugs are computed on `GridToMesh(shell ∩ box)` (28k faces, 1 s) instead of the full helmet.

## Splitting into printable parts (seam, magnetic tabs, crown)

Verified on the 400 mm king head (face body + back hair panel + crown + eye plugs):

- **Ask for the real print size against a reference object** the user already printed (here a 260 mm
  mask). Fit tests in a scaled model are worthless if the slicer scale differs; import the reference
  into the scene in mm and compare.
- **Splitting fixes "the head does not fit"**: with a back panel the user puts the face on and closes
  the back, so the bottom opening no longer limits the size.
- **Hidden seam = cheapest path in the grooves**: Dijkstra on the outer-surface edge graph, edge cost
  low where the surface is concave (mean `n·(p_u-p_v)/|p_u-p_v|` per vertex), high on ridges; waypoints
  on both sides below the rim and across the back under the crown band. Resample at 2.5 mm, smooth.
- **Cut with SDF, not Mesh Boolean**: a 0.6 mm sheet blade made of overlapping boxes or a ribbon swept
  along the seam either did not separate the parts (EXACT treats a thin open sheet as nothing), produced
  a 100-face fragment, or kept Blender at 100% CPU for minutes (MCP timeout, the app shows the server as
  failed until Blender answers again). What worked: a closed 1.6 mm ribbon solid directed horizontally
  towards the vertical axis (not along the surface normal), `MeshToSDF(helm, 0.8) − MeshToSDF(ribbon)`
  → two components in 5 s.
- **Magnetic tabs like a Spider-Man helmet**: blocks 25×30 mm fused to the body's inner wall, reaching
  under the panel with 1 mm play (SDF: `tabs − dilate(panel, 1 mm)`), a 10.5×3.4 pocket in each tab and
  the coaxial pocket in the panel's inner wall so the magnets meet face to face. Measure the wall depth
  by ray casts on both sides at every tab (34 mm under the crown vs 17-20 elsewhere) and size the tab to
  the deeper one.
- **Crown off for printing**: a flat cut at the crown base hits the seam and the upper tabs. Cut 10 mm
  up inside the band and separate only the band component (largest radius) from the upper slab, then
  body = full − crown in SDF: the 10 mm ring left on the body becomes a self-aligning socket.
- **Glasses magnets**: 10.5×3.4 pockets flush with the surface on the nose bridge and both temples
  (ray cast from the front at x = 0 and ±78 mm); the client glues matching magnets in their sunglasses.
- `bpy.ops.wm.save_mainfile()` drops node groups with no users: set `use_fake_user = True` on helper
  groups you will re-run.

## Workbench renders for the client

`BLENDER_WORKBENCH`, studio light, single colour, cavity BOTH, shadows, `shading.background_type='WORLD'`
with `world.color` light grey (the VIEWPORT background type is ignored in renders). A temporary camera
aimed with `(-d).to_track_quat('-Z','Y')`; 2.6 m for a 1 m head at 60 mm. Shots that answer the
client's questions: front, three-quarter, side, back, eyes removed with plugs beside the head, from
below into the cavity. Restore every scene setting afterwards.

## MCP for Blender pitfalls (cost hours)

- **Grid to Mesh `Threshold` defaults to 0.1 → empty mesh.** Set it to 0.0 on every Grid to Mesh node.
- **Mesh to SDF Grid needs a closed mesh**: an open Tripo mesh (boundary edges) gives nothing. Use a
  closed remesh for the SDF and the dense original only for measurements.
- **Object Info returns evaluated geometry**: pointing it at an object that still has a modifier gives
  you that modifier's output. Make a modifier-free object sharing the mesh datablock.
- **Object Info transform space**: with `RELATIVE`, moving the output object shifts the helpers but not
  primitives made inside the tree (a Cube node box missed the head → empty plugs). Use `ORIGINAL` when
  helpers already sit in world space.
- Multi-input socket names: SDF Boolean UNION/INTERSECT take everything on `'Grid'`; DIFFERENCE has
  `'Grid 1'` and `'Grid 2'`. Mesh Boolean: `'Mesh 1'`/`'Mesh 2'` for DIFFERENCE, `inputs[1]` for the
  others. Access by name, `inputs[...]` by identifier does not work.
- **Setting modifier inputs from Python does not re-evaluate**: toggle `md.show_viewport`, then
  `obj.update_tag(); bpy.context.view_layer.update()` before reading `evaluated_get`.
- **MCP calls time out around 60 s** but Blender keeps computing: run heavy evaluations alone in a
  call, then poll with a light call. bmesh on 2M vertices is one such heavy call; prefer numpy
  `foreach_get` for measurements.
- The viewport can show a second object at the same place (an old version, a hidden-but-rendered bake):
  z-fighting looked like a closed hole. Hide old versions, move plugs 35 cm in front of the face.
- Orientation check for boolean operands: signed volume Σ a·(b×c)/6 > 0 means outward normals.
  Booleans were never the problem; wrong depth sign and a reinforcement pad deeper than the cutter were.
- `look`/screenshots mislead on hollowness; the numeric section test (`spans()` in the script) does not.

## Files

- `scripts/wearable_head_build.py` - the full build (profiles, skirt, cutters, eyes, pockets, two
  Geometry Nodes variants, output objects, report). Re-run it in Blender's Text Editor after changing
  `SCALE_CM`; modifiers start disabled because the first evaluation takes 15-30 s.
- `reference/geometry-nodes-sdf.md` - node ids, sockets and the small Python helpers to build and
  measure the tree.
