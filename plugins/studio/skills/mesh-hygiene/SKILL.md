---
name: mesh-hygiene
description: General rule for ALL 3D modelling work (Blender, scans, Tripo/AI models, booleans, remesh, sculpt, cuts, imports, STL/OBJ/FBX/GLB export for printing or games) - check and clean dirty geometry before handing a mesh over or exporting it, and report the numbers - duplicate vertices and edges, degenerate or zero-thickness triangles, non-manifold edges and holes, bowtie vertices, flipped normals, tiny loose islands. Includes a background Blender script that checks and cleans, and what "clean" means for print vs game meshes. Read it at the start of any session that touches 3D models.
---

# Mesh hygiene (every 3D job, user rule)

Every time a mesh leaves your hands (export, delivery to a client, hand-off to another tool or agent, or before
reporting a modelling step as done), check it for dirty geometry, clean it, and put the numbers in your report.
Boolean operations, voxel remesh, decimation, sculpt, cuts, mirror/merge, AI generators (Tripo) and imports all leave
defects that Blender's viewport does not show and that only appear later in a slicer or game engine.

## What to check (numbers, before and after)

| Defect | How to measure | Why it matters |
|---|---|---|
| duplicate vertices | positions rounded to 0.001 mm, count repeats | hidden seams, non-manifold edges, broken normals |
| duplicate edges / faces | same vertex pair or set twice | slicer errors, z-fighting |
| degenerate triangles | after triangulating: area < 1e-8, or height (2*area / longest edge) < 0.001 mm | slicers report "zero-thickness geometry", engines get NaN normals |
| non-manifold edges, holes | edges with != 2 faces | not watertight: slicer guesses, booleans fail |
| bowtie vertices | two fans of faces touching in one vertex | non-manifold in slicers, breaks booleans |
| flipped normals | signed volume < 0, or normals inconsistent with neighbours | inside-out prints, black faces in games |
| loose specks | islands with a handful of vertices | stray blobs in the slicer, wasted draw calls |
| volume | `bmesh.calc_volume()` before/after cleaning | proves the cleaning did not change the part |

"0 non-manifold" in Blender is not enough: a 2-million-triangle mask body with 0 non-manifold edges still had
1060 zero-thickness faces and 738 doubled vertices, which OrcaSlicer flagged only at slicing time.

## How to clean (Blender, background run on a copy)

`scripts/mesh_clean.py`:

```
blender -b copy.blend --python mesh_clean.py -- <out_dir> [object names]          # check + clean + STL export
blender -b copy.blend --python mesh_clean.py -- <out_dir> [object names] --check  # report only
```

Steps it runs: triangulate; `remove_doubles(0.002)` + `dissolve_degenerate(0.002)`, collapse the shortest edge of
faces that are still flat (three passes); then until manifold: delete two rings of faces around each non-manifold
edge, `split_edges` on bowties, `holes_fill(sides=0)`, triangulate, merge by 0.0005; delete islands under 50
vertices; recalc normals. On 1-2 M-triangle print parts the volume changed < 0.5 cm3 and pins/sockets stayed intact.
Then swap the cleaned mesh data into the live file (load the objects from the cleaned blend, assign their `data` to
the live objects, remove the orphans) and re-export from there.

Heavy meshes: run it in a background Blender, not through an MCP call (60 s timeout).

Big boolean results (a 2.6 M-triangle base with several Tripo parts unioned in) can need many repair rounds: each round
fills holes that open new bad edges nearby. The script loops up to 30 rounds; always read the DOPO line and run it
again on `cleaned.blend` if non_manifold is still above 0.

## Print vs game meshes

- **Print (STL/3MF):** everything above, and the result must be watertight (0 non-manifold, positive volume).
  Also check wall thickness where you cut or sculpted (a sculpted base went down to 0.2 mm).
- **Games (FBX/GLB/OBJ):** duplicates, degenerate triangles, flipped normals and specks matter; open meshes are
  fine, so do NOT fill holes on purpose-open geometry (planes, cards, foliage). Keep UV seams: merge doubles only
  with UV-aware tools, or the seams collapse.

## Report format

Per part: faces, duplicate vertices, degenerate faces, flat faces, non-manifold edges, specks removed, volume
before -> after. One line each; say plainly if something could not be fixed.
