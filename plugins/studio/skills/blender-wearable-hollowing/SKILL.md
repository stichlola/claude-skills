---
name: blender-wearable-hollowing
description: Turn a solid sculpt (Tripo or any dense mesh) into a 3D-printable wearable shell in Blender - hollow it with Geometry Nodes SDF grids, open the bottom without touching the visible outline, extend hair or a collar, cut removable parts (eyes) with magnet pockets at real-world millimetres, verify fit with numbers, bake a real mesh for hand sculpting, render client previews, scale the head to a real accessory (glasses: blind arm pockets with tolerance), rebuild magnet pockets at real size after scaling and perpendicular to the joint, check every pocket with axial profiles and the assembled parts for interference, fit-test a scanned head and carve room locally. Includes the MCP-for-Blender pitfalls (empty Grid to Mesh, Object Info spaces, no re-evaluation after Python edits, call timeouts) and a full working build script. Use for mascot heads, helmets, masks, cosplay shells, any "make it hollow so a person fits inside" job, and whenever driving Blender 4.x/5.x through MCP with SDF or boolean nodes.
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
- **The pocket axis must be the normal of the joint face, not "horizontal towards the axis".** The first
  version used the horizontal direction: the holes looked round and clean but entered the tab face at
  17-40°, so on one side the wall was 1-2 mm high and the panel had almost no pocket (the magnet would
  have sat half in each part). Found only by the profile check below, months later. Correct recipe per
  tab: `Q` = panel inner surface on the old axis, `n` = mean panel normal on rings r = 0/3/6 mm around it
  (pointing body → panel), `P` = first body surface from `Q` along −n (gap must read 1.0 mm). One
  cylinder Ø10.5 along n from `Q − n·(gap + face_drop + 3.3)` to `Q + n·(panel_drop + 3.3)`, where the
  drops are how much the curved faces fall below the plane over the 11 mm ring. Search the best centre on
  a ±10 mm grid on the joint plane, scoring min(material behind the tab, material behind the panel)
  measured along n; require ≥ 4.2 mm on both sides. Where nothing qualifies (here the two top tabs:
  panel 0.7-1.3 mm thick along n) leave the tab as an alignment support without a magnet and say so.
- **Re-doing pockets**: fill the old ones first, else the new hole merges with the old crescent. Panel:
  `old_cyl ∩ panel_without_holes` (the raw panel before seats) unioned back. Body: `old_cyl ∩ tab_boxes
  − dilate(panel crop, 1 mm)` (SDF offset on a 40 mm crop around each seat, voxel 0.2) so the fill does
  not close the 1 mm play. Then cut the new cylinders at radius +0.02 mm: cutting exactly on a filled
  surface leaves non-manifold edges, and a fan "repair" of them half-fills the pocket.
- **Tell the user to glue magnets flush with the pocket mouth**, not at the bottom: pockets are deeper
  than the magnet where the face is curved, and at the bottom two 10×3 discs end up 3-7 mm apart.
- **Crown off for printing**: a flat cut at the crown base hits the seam and the upper tabs. Cut 10 mm
  up inside the band and separate only the band component (largest radius) from the upper slab, then
  body = full − crown in SDF: the 10 mm ring left on the body becomes a self-aligning socket.
- **Glasses magnets** (first idea, later dropped by the user): 10.5×3.4 pockets flush with the surface on
  the nose bridge and both temples; the client glues matching magnets in their sunglasses.
- `bpy.ops.wm.save_mainfile()` drops node groups with no users: set `use_fake_user = True` on helper
  groups you will re-run.

## Scaling the head to a real accessory (glasses) and rebuilding every pocket

Verified on the king head: 400 mm → 375 mm so a real pair of glasses (STL from the user) fits.

- **Scale factor from the accessory, not by eye**: lens centres from the front frame (raster the frame
  verts in x-z at 1 mm, flood-fill from the border, the enclosed empty cells are the lenses; centroid per
  side) vs the head's eye centres (from the eye plugs, mirrored about x = 0). Here 72.2 / 77.1 = 0.9365.
- **Work in the body's local frame.** Parts that were moved apart for display (panel, plugs) keep their
  mesh in the body frame with only an object offset: scale every mesh about its local origin by the same
  factor, keep the object transforms. A BVH from `BVHTree.FromObject` is in LOCAL coordinates - casting
  world-space rays into it gave nonsense hits until fixed.
- **Magnets never scale.** After scaling, rebuild each pocket at its real size at the scaled position:
  take the original cutter components (real size) and translate each by `(S−1)·centroid`; the scaled old
  hole is always inside the new one, so a plain DIFFERENCE is enough. A pocket that is no longer wanted
  (nose) is filled with `original_unscaled_surface_mesh(scaled) ∩ cylinder(old pocket ×1.06)` unioned
  back: the nose comes back with its real surface, only a faint outline to sand.
- **Placing the glasses**: centre at x = 0, lens centres on the eye centres, then push the frame back
  until its closest vertex is 1 mm in front of the face (`dy = min(face_y(x,z) − 1 − frame_y)` over the
  frame vertices, face found by +y ray casts).
- **Arms cannot go through**: on a 375 mm head the arm (x ≈ ±63 mm) enters the face at the temple and
  the wall there is ~28 mm; behind it is the wearer. Make **blind pockets**: box around the straight
  part of the arm + 0.3 mm per side (here 3.3 × 10.8 mm), from 15 mm in front of the surface to
  2.5 mm before the inner wall, and tell the user the arm length to cut to (here 34 mm from the hinge).
  The hooked ear end cannot pass a slot: it is cut off anyway.
- **Check the result with a trimmed copy of the glasses** (bisect the arm at the pocket end, mirror the
  straight arm if the STL has one folded): BVH `overlap()` with the body must be 0, min distance of the
  arms to the pocket walls ≈ the tolerance. A raster section of each pocket (`inside()` on a 0.25 mm
  x-z grid at a fixed y) shows leftovers immediately: one pocket had a 2 mm wedge left by the user's
  manual fill of the nearby temple magnet seat; re-cutting the pocket cutter fixed it.

## Fit test with a real head and making room locally

- Test head: `.3D_ScanStore_Free+Head/OBJ/Head.obj` (metres → ×1000, rotation x 90°, face −y). Eye
  midpoint in its local frame (0, 0.2984, 0.0984). Place the eyes on the king's eye centre + (0, back,
  dz) and scan a small grid (back 40-55 mm, dz 0 to −12 mm): for each, count head vertices inside any
  part (parity ray cast, only where `find_nearest` < 15 mm) and the minimum distance. Report the
  clearance per region (nose/mouth, chin, forehead, temples, top, back).
- Scaling the head 6 % down took the minimum from ~1 cm to 1-3 mm: always re-test after any scale.
- **Make room without touching the outside**: envelope = test head (holes filled) → Mesh to SDF (voxel
  1 mm) → SDF offset +10 mm → mesh; intersect it with region boxes (upper back where the top tabs are,
  chin/beard inside, nose) and subtract from the body. Check the magnet pockets stay ≥ 5 mm from the
  envelope and measure the wall left behind the carve (ray along the envelope normal). Result here:
  minimum clearance 3 → 10 mm everywhere.

## Verifying pockets and fits (do this before saying "done")

- **Axial profile per pocket and per part** (`scripts/seat_check.py`): along the pocket axis every
  0.5 mm, mark `#` if the axis point is inside material (bottom), `o` if all 12 points of a ring at
  r + 0.35..0.7 mm are inside material (full wall), a letter/digit for partial walls, `.` for air. A good
  pocket reads `###oooooo` from the bottom: at least magnet thickness of `o`. Partial digits right after
  the bottom mean the pocket is tilted against the face. Diameter alone (ray to the wall) always looked
  right and hid the problem.
- **Pair check**: both pockets of a pair come from one cylinder (coaxial by construction); report the
  depth of the full-wall part in each piece and the distance between magnet faces when glued flush and
  when glued at the bottom.
- **Assembled interference**: build BVHs from the raw mesh coordinates of each part (they share the
  body frame) and run `overlap()`. Crown on its seat: contact only (≤ 0.1 mm). Eye plugs were 0.3-0.4 mm
  too big for their holes (zero clearance in the original design plus the scaled rim): fixed with
  `plug − dilate(body crop around the eyes, 0.25 mm)` (SDF voxel 0.08) and then the plug magnet pockets
  deepened by the same amount (+0.7 mm) so the 2 mm magnets still fit. Target: 0 overlaps, ≥ 0.2 mm.
- A parity `inside()` test can report solid inside an empty pocket on thin shells: confirm with a ray
  along the pocket axis and by counting faces inside the cylinder before "fixing" anything.

## Magnet sizes used (real mm, never scaled)

| Use | Magnet | Pocket | Depth | Notes |
|---|---|---|---|---|
| Body ↔ back panel tabs | 10×3 N52 disc | Ø10.5 | 3.3 per side + face drop | 4 pairs; top tabs without magnet |
| Eye plugs ↔ eye rim | 5×2 N52 disc | Ø5.5 | 2.4-3.0 (plug side +0.7 after the clearance cut) | radial, top and bottom of each eye, 8 total |
| Glasses arms | none | 3.3×10.8 blind slot | to 2.5 mm before the inner wall | 0.3 mm play per side, arms cut to length |

Shopping list for one head: 8× 10×3 + 8× 5×2, buy packs of 20 of each. Mark polarity on each stuck pair
before gluing.

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
- **Manifold boolean solver** (`md.solver = 'MANIFOLD'`, Blender 4.5+) does 1-2M-face differences in
  2-6 s where EXACT hangs. Inputs must be manifold: count edges with ≠ 2 faces via
  `np.bincount(loops.edge_index)` first and repair (or use EXACT on tiny meshes like eye plugs).
  It silently returns the input unchanged when the target is a soup of overlapping closed shells (a
  Tripo model can be 100+ shells): split the shells first and cut only the one that needs it.
- **Heavy work in a separate background Blender** (`blender -b file.blend --python job.py -- args`,
  write the result with `bpy.data.libraries.write(path, {obj}, fake_user=True)`, then append it): long
  modifier applies in the live Blender froze the UI, the user closed it twice thinking it had crashed.
  Save the live file first, and remove previous result objects in the job so names don't get `.001`.
- `BVHTree.FromObject` is in object-local space; use `FromPolygons` on raw mesh coords when several
  parts share a frame but have different object offsets.

## Files

- `scripts/wearable_head_build.py` - the full build (profiles, skirt, cutters, eyes, pockets, two
  Geometry Nodes variants, output objects, report). Re-run it in Blender's Text Editor after changing
  `SCALE_CM`; modifiers start disabled because the first evaluation takes 15-30 s.
- `reference/geometry-nodes-sdf.md` - node ids, sockets and the small Python helpers to build and
  measure the tree.
- `scripts/seat_check.py` - pocket axial profiles, pair report, assembled-overlap check and test-head
  fit scan; run in Blender with the object names edited at the top.
