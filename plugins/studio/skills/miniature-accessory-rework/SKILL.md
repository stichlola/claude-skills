---
name: miniature-accessory-rework
description: Add or replace costume parts on an existing AI-generated (Hi3D/Tripo/Gemini) or scanned resin miniature in Blender, measured with ray casts instead of guessed - remove an old part with ray cross-sections and a lofted cutter, relief capes built as heightfield slabs, wrist rings/covers as shells from ray-measured sections, lathe tassels, curve cords, one MANIFOLD collection union, then remesh pitfalls (inner voids, volume growth), the sculpt-on-hidden-active-object trap, and client renders (grey resin, WoW-style backdrop, contact sheet without white gaps). Use for client change requests on a figure ("add a cape/cords/tassels", "new hand pose", "make it closer to the concept"), regenerating parts with Gemini + Hi3D, and preparing renders for approval.
---

# Reworking a miniature: new parts on an existing figure

Learned on a 44 mm WoW warlock for resin (Nov 2026). 1 BU = 1 mm (scale_length 0.001). Always work on a copy
(`_v2`, `_v3`), never overwrite the client file. Read `mesh-hygiene` first; report its numbers before any export.

## 1. Decide: model it, or regenerate it

- Small additions (cords, tassels, rings, an emblem, a cape pattern) -> model them on the existing mesh (sections 2-5).
- A new pose of a hand/arm, or "make it closer to the concept" -> regenerate the figure: give Gemini the client
  concept + a clean A-pose render of the current model, ask it to pose the character while keeping every detail,
  then Hi3D/Tripo. Ask the client clarifying questions first (which hand, how the prop is held, may angles change).
  Compare the result side by side with the concept image before touching Blender.
- Generated parts arrive at any scale: scale to the agreed height (measure the world bounding box), hide the old
  model, keep it in the file.

## 2. Measure with ray casts, not by eye

- `BVHTree.FromObject` + repeated `ray_cast` along a line gives the cross-section hit list (enter/exit pairs).
- Inside test: cast from the point; if the first hit has `normal . dir > 0` you are inside.
- Limb sections (wrist, neck): start from a guessed centre, cast 24-36 radial rays in the plane normal to the limb
  axis, set the centre to the centroid of the hits, repeat 3-4 times; this gives centre and radius per slice. For a
  bent hand use the wrist->knuckle axis, not the forearm axis.
- Old part to remove (an old cape): sample its back surface y(z) with rays at several heights, build a lofted cutter
  solid just behind the body (+0.3 mm margin), MANIFOLD DIFFERENCE. Then delete leftover small islands (they sit
  where the cutter was tangent, e.g. near the base).

## 3. Parts that follow the body

- **Cape / panel with relief:** a heightfield slab on a regular (u, z) grid: inner surface = sampled body back
  (smoothed, minus 0.35 mm) with curled edges, outer = inner + thickness + relief. The relief comes from distance
  fields (KDTree to polylines of the pattern: lattice, border, emblem, scrolls) through a smoothstep profile. Put
  per-face material indices and a float point attribute (`rilievo`) on it so a shader can colour raised parts.
  Keep relief at least 0.5 mm high and lines at least 0.4 mm wide for resin at 1:50-ish.
- **Rings, cuffs, covers:** build the shell directly from the measured section radii (closed tube: inner r - 0.15,
  outer r + 0.2..0.38 for a flare). Do NOT region-grow the body surface and solidify it: it catches the hand and
  sleeve and makes spikes (even-offset solidify on noisy AI meshes = huge spikes).
- **Tassels:** lathe. A polyline profile in XZ + SCREW modifier (axis Z, 36-40 steps, merge vertices) -> clean
  manifold solid. Knot = UV sphere r 0.6.
- **Cords:** a curve along a dense path snapped to the surface (pick the ray hit nearest the expected depth), bevel
  depth 0.5 with fill caps. Its mesh is non-manifold by itself, but it unions cleanly.

## 4. Join

- Put all parts in one collection and do a single MANIFOLD boolean UNION with `operand_type='COLLECTION'`. Faster and
  cleaner than many pairwise unions.
- Then: components (delete specks), thickness sample (rays inward from surface points): flag anything under 0.8 mm
  to the user instead of silently thickening.

## 5. Remesh after joining generated parts

- Voxel size from area: `sqrt(area / target_faces)` (1.5-3 M faces for a 45 mm figure).
- Voxel remesh creates **inner void islands** (closed bubbles inside the body): delete every island except the
  largest, after checking where they are (do not assume small attached parts are the islands).
- A bigger voxel fills gaps narrower than the voxel: the "light" remesh (0.06 vs 0.042) grew volume by ~10 % and
  closed gaps between fingers. Compare volume and check fingers/props before choosing.

## 6. Sculpt trap

Sculpt mode works on the **active** object even if it is hidden. If brushes "barely work" or "act at the wrong
scale", check `context.active_object`: it was a hidden older remesh with another copy (old cape collection)
overlapping. Fix: exclude stale collections from the view layer (`layer_collection.exclude = True`), hide the
rest, make the target active, re-enter Sculpt.

## 7. Client renders

- Cycles GPU, 128 samples, denoise, AgX, look "Medium High Contrast", exposure ~+0.8 (default looked dull grey),
  shadow-catcher floor, area lights re-aimed at the figure centre. Grey resin material: the client sees what prints.
- Views: front, 3/4 front, back, 3/4 back + close-ups of what changed (check each close-up frames the right part).
- Styled backdrop (e.g. WoW): render with `film_transparent=True` into one folder, composite the background in PIL
  into a second folder, so background changes need no re-render. Dark neutral radial gradient read best; coloured
  rim lights (purple/fel green) look good on dark purple but tint a grey figure on a neutral background. Avoid
  sparkles (read as snow).
- Contact sheet: rows scaled to the same height so each row fills the sheet width exactly, thin gaps in the
  background colour, no white holes.
- Draft message to the client (English), user sends it.

## 8. Splitting a big statue for shipping (dragon wings, Nov 2026)

- Voxelize first (parity ray fill along one axis, 0.5 mm) and find the real contacts with connected-component
  tests: AI wings are fused along the back far lower than they look (membrane root down to z~62 on a 207 mm dragon),
  so a box-limited plane beside the spine does not free them. A min-cut on voxels tends to slice through thin
  membrane: use it only to locate joins, not as the seam.
- Wing cut that hides well: a thin swept "ribbon" cutter (kerf 0.1 mm) crossing the membrane 1-2 mm outboard of
  the back, following the root along the spine spikes, plus a flat clipped disc across the wing arm 8-10 mm from the
  shoulder (clean round section, room for pins). Check both ribbon edges are in air with BVH inside tests.
- Pins only where the section is thick (arm, 12 mm): 2 per wing, D4 + D3 separate printed pins, 0.12 mm radial
  clearance, walls >= 1 mm measured with radial rays; membrane edges get glued.
- After MANIFOLD booleans on an AI mesh, test assembled interference: self-intersections leave 0.05 mm slivers;
  subtract the body from each wing (MANIFOLD) to clear them. Skip the base-disc cut when an ornament is fused across it.
- Fast path without agents or Blender: `pip install manifold3d trimesh pymeshlab`. Load the STL with trimesh, wrap
  it in `manifold3d.Manifold(Mesh(vert_properties=float32, tri_verts=uint32))`: a 1.2 M-face body loads in ~3 s and a
  disc-limited plane cut (`M ^ cutter`, `M - cutter`, `decompose()` for islands) takes well under a second.
- Interactive add-ons (CatPin etc.) are mouse/modal tools, not scriptable: the user draws, we check and render.
- Body joints (Nov 2026, Karna v3): base cut as a heightfield in coordinates sheared along a tilted assembly
  direction (no undercut by construction, legs over the tail block a vertical pull); neck as a plane limited to a
  disc; D5x14 pins along each joint direction, walls by rays on the uncut skin (rays on the slanted cut face give
  false negatives). Check assembly order: the head pulled along its axis hit the mounted wings -> head before wings.
- Joints that hold WITHOUT glue (resin, Nov 2026; researched online): resin is brittle, so no snap fits. Use
  pins for alignment + 2 neodymium magnets (8x3) per joint for hold; only the magnets get CA glue in their pockets.
  - Ribbed press-fit pins: core d/2 (0.12 radial clearance in the d+0.24 hole), 3 ribs 0.6 mm wide reaching
    0.10 mm beyond the hole wall, 1.5 mm ramps and 0.4 chamfers at both ends. Build = (core + ribs) INTERSECT a
    revolved envelope profile. Tell the user to test-print one pin + hole and adjust the rib interference
    (0.05 tight printer / 0.15 loose).
  - Magnet pockets: dia 8.2, depth 3.2 (magnet 0.2 below the face), axis = joint assembly direction, walls >= 1.2
    tested as `(shell_cylinders - (lo + hi)).volume() < 0.3` against the ASSEMBLED pair (testing each piece alone
    fails on an uneven heightfield seam), >= 8.2 mm (perpendicular) from pin holes, pair as far apart as possible.
    On a flat neck cut sample a grid on the plane; on curved seams sample cut-face centres (normal . d < -0.97) near
    the other piece (cKDTree, NOT trimesh closest_point: 2 GB on 1 M faces). Verify by volume removed per piece.
  - Script: `scripts/perni_magneti_manifold.py` (Karna, runs in ~30 s on 1.4 M faces total). Remind the user to
    mark magnet polarity before gluing.
- Undercut-free cuts by construction (Kala, Nov 2026): any cut that must slide off along d is a heightfield in a frame
  with one axis = d (base: d = +z; wings: d = arm axis). For wings: split first with a voxel bisector (EDT(body) - EDT(wing),
  marching tetrahedra), then voxelize wing and "rest" (body + other wing) in the d-frame and per column cut at the top of
  the rest below the wing top; max-filter G (5x5) where there is no wing, or the interpolated slopes shave 0.2 mm skin
  slivers off neighbouring spikes (hundreds of islands). A plain bisector or a sleeve around an arm stub always
  interferes 0.1-45 mm3 when pulled. Scripts: kala_pezzi/script/kl1b_ali_hf.py, mt.py (marching tets), vox.py (winding voxelizer).
- Base seam on a decorated plinth: if the rocks sit on a moulded band, cut 0.3 mm above the band's top rail (natural
  groove), drop F to the flange top under ornaments that hang over the band so they stay whole on the upper piece.
- STL written by trimesh reloads as triangle soup: `merge_vertices()` before building a Manifold, else NotManifold and
  every boolean/interference silently returns 0.
- Thin wing arms (inscribed r ~3 mm): even D3 pins with 1 mm walls may not fit; say so instead of forcing it.
- Speed stack (installed Nov 2026, `pip install --user manifold3d trimesh open3d embreex pymeshlab`):
  manifold3d for booleans/cuts/hulls, `open3d.t.geometry.RaycastingScene` for rays (200k rays on 600k faces
  in 0.4 s; also `compute_occupancy` / `compute_signed_distance` instead of voxel parity fills), trimesh with
  Embree for simple queries. Use Blender only for renders and .blend files. Commercial alternatives seen:
  MeshLib (fast, paid licence for business), Meshy Auto Split API / Hi3D Split-to-Print (automatic splits with
  connectors, but seams not placed to hide on statues).
