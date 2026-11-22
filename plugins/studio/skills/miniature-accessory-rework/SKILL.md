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
