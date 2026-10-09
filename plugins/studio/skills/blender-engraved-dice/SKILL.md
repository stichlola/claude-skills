---
name: blender-engraved-dice
description: Make custom polyhedral dice with engraved words for 3D printing in Blender - rebuild a clean die from a supported/numbered STL, bevel edges, place one text block per face (centred, upright, fitted inside the triangle), engrave by SDF in under a second instead of hanging Blender with exact booleans, or hand the user the text cutters to do the difference, make paint masks (stencils) per face, and orient/support the die for resin printing without marking the faces. Verified on a D8 (octahedron); the method extends to any die with flat faces. Use for D4/D6/D8/D10/D12/D20 with words or symbols, "oracle"/decision dice, custom numbers, and any engraved text on flat faces of a printed object.
---

# Engraved dice in Blender (D8 verified)

Lessons from a 27 mm "decision" D8 with eight Italian phrases (FALLO!, CHIAMA LE AMICHE, ...) driven
through MCP for Blender 5.1, printed in resin with gold-filled engravings.

## Hard rules

- **Ask whether the user wants the boolean done or left to them.** This user wanted the text solids
  placed on the faces and to do the difference themselves. Default: deliver die + text cutters as
  separate objects, plus an already-engraved copy only as a reference.
- **Never start from the supplied STL if it has supports or numbers baked in.** Measure it, then build
  a clean solid from the measured planes (see "Rebuild"). Keep the original untouched.
- **Units are millimetres** even if Blender says metres; never rescale the scene.
- Work on the object the user points at ("the die on the right") - check positions with
  `matrix_world.translation`, there are often several copies.

## Rebuild a clean die from a messy STL

A D8 STL with supports and recessed numbers: cluster face normals near the 8 directions
`(±1,±1,±1)/√3`; for each, histogram `n·centre` of the faces - the mode is the face plane, the minimum is
the recess depth (here 0.5 mm). Solve the 6 vertices by least squares from the 4 planes meeting at each
one. Then build the regular solid from scratch (6 verts, 8 tris for a D8) with the same planes, so faces
are exactly where the original's were.

## Bevel

`bmesh.ops.bevel(geom=verts+edges, offset=0.6, segments=4, profile=0.5, affect='EDGES', clamp_overlap=True)`
on the clean solid (27 mm D8 -> 0.6 mm). Do it before engraving; keep the text at least 1.5 mm from the
face edges so the bevel never cuts a letter.

## Text per face

- Frame per face: `n` = face normal, `up = normalize(Z - n*(n·Z))` (upright when the die stands on a
  vertex; for down-facing faces this still reads upright), `right = up × n`. Matrix columns
  `(right, up, n)`; origin at the face centroid.
- Text curve: `align_x/align_y = 'CENTER'`, `extrude = (depth+0.3)/2`, placed so it spans from 0.3 mm
  outside the face to `depth` inside (0.5 mm). Convert to mesh, `remove_doubles(1e-4)`,
  `recalc_face_normals`.
- **Fit inside the triangle**: block centre at ~0.29 of the triangle height from the long side (not the
  centroid at 1/3: more room), shifted towards the base; grow the size while
  `width + 2*1.5 mm <= triangle_width_at(top of block)` and `height <= 0.55*H`.
- **Font**: a bold, narrow serif. Times New Roman Bold beat Georgia Bold (narrower -> bigger letters).
  Letters came out 1.1-1.7 mm tall on a 19.6 mm edge. Below ~1 mm the 0.5 mm engraving is too thin to
  fill with paint - say so and offer a line break ("FREGA-/TENE") or a condensed font (Cinzel, Bebas).
- **Letter spacing ≥ 1.06**: glyphs that touch or overlap (Georgia at 1.12 still overlapped) make the
  text mesh self-intersecting; check with `BVHTree.FromBMesh(bm).overlap(itself)` == 0.
- Long phrases on two lines (`\n`, `space_line 0.92`); a single symbol ("?") can be much larger.

## Engrave (if asked)

- **Exact Mesh Boolean is the trap**: 8 text solids with 10-17k faces each, applied one by one, either
  produced garbage (a 733-face fragment, a 0-face result) when the text self-intersected, or, with
  `use_self=True`, kept Blender busy long enough to time out MCP and then crashed it.
- **SDF instead** (Geometry Nodes, < 1 s): join all text solids in one object, then
  `MeshToSDF(die, voxel 0.07) − MeshToSDF(texts, 0.07) → GridToMesh(threshold 0)`. 0.07 mm voxels keep
  serifs sharp; result ~500k faces, manifold. Object Info in `RELATIVE` space when the texts are stored in
  world coordinates.

## Paint masks (stencils for filling the engravings)

Per face: a plate = the exact face triangle lifted 0.05 mm off the face and extruded 1 mm outwards
(covers bevel too), plus a "tall" copy of that face's text remapped along the normal to span
−0.2..+1.5 mm so it cuts through the plate. Plate − tall text = stencil with open letters. Name both
after the phrase; when texts change, rebuild the tall texts and re-match plates by the sign of their
centroid offset, not by old names.

## Printing (resin)

Stand the die on a vertex, no tilt. D8 faces are ~55° from the plate, self-supporting at this size.
Supports only on the bottom vertex (medium) and on the 4 lower edges + 4 equator vertices (light tips
0.3-0.4 mm); the bevel hides the marks and the faces stay flat (balance). Never rest a face on supports
(one phrase ruined) or an edge (two faces need supports). Biggest cross-section is the equator - slow
the lift there if it peels badly.

## Files

- `scripts/engrave_die.py` - parametric D8 build: clean solid, bevel, fitted text per face, joined
  cutters, paint masks, optional SDF engraving. Change `TEXTS`, `EDGE_MM`, `FONT_PATH`, `ENGRAVE`.
