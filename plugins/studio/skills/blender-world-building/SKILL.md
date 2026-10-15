---
name: blender-world-building
description: Build and edit a game's open world in Blender and ship it to Unreal (or any engine) - moving whole ripped levels by a layout file, generating terrain that closes a city in mountains and joins existing ground seamlessly, a painted vertex-color mask material (sand / earth rock / grey rock / meadow) with Vertex Paint brushes, Weight Paint brushes that scatter kits (grass, reeds, trees, rocks, houses) with Geometry Nodes, procedural towns, tunnels and signs, exporting scatter as instance placements instead of merged meshes, a matching triplanar terrain material in UE, automatic hole detection, and the Blender MCP / headless traps met on the way. Use when the user wants to lay out, sculpt, paint, populate or fix a game map in Blender, or bring Blender world edits into a game engine.
---

# Blender world building for a game

From jak3-ue5: Haven City and the desert of Jak 3 joined into one open world, edited by the user in
Blender and brought into Unreal Engine 5 by scripts. Scripts live in the project's `tools/blender/`
(`world_editor.py`, `world_export.py`, `apply_world.ps1`, `haven_terrain.py`, `faraway*.py`,
`haven_countryside.py`, `haven_holes.py`, `tunnel.py`); the patterns below are what to reuse.

## The editing scene

- **One .blend built by a script** (`world_editor.py`): reference levels locked (`hide_select`),
  movable groups as **empties** with the ripped level pieces parented under them (an empty per
  district plus one for the whole city), and a `Custom` collection for everything new. Solid shading,
  `clip_end` 20 km: maps are kilometers wide, the default clip cuts them.
- **Layout = a JSON the game reads** (`WorldLayout.json`): each group's world transform in Blender
  meters and, precomputed, in engine units (UE: x·100, -y·100, z·100 cm; Blender +Z turn = UE -yaw).
  The game moves whole levels by it at load; nothing in the level files changes.
- A user's "Save as" makes `world_edit1.blend`: export from the **newest** `world_edit*.blend`.
- Heavy .blend (140 MB+) opened in the user's Blender takes a minute; **long `execute_blender_code`
  calls time out (~2 min) while Blender keeps working** - wait and query again instead of resending.
  Anything that copies hundreds of thousands of faces through Python lists can crash the user's
  Blender: run it **headless** (`blender -b file.blend -P script.py`) and `wm.revert_mainfile()` the
  live one after, or work with numpy `foreach_get/foreach_set`.

## Terrain that closes a map

- Grid mesh (16-24 m cells) over a region; per cell a **ray scan of the existing levels**: city cells
  (skip), water to keep (skip), and under every other mesh the ground stays **1.5 m below its lowest
  surface** (hidden in front, fills behind open shells). Open (one-face) edges of big meshes pin the
  ground 0.5 m under them; pins only from meshes ≥ 60 m across, or plants/pebbles pull up cones.
- Relax the free cells (Jacobi, 1500 passes, capped under the rock) toward a target floor: street
  level near the city, sinking under the sea past the coast.
- Mountains: chains as polylines + **mass rectangles**, filled with creased cones
  `cone = clip(1 - dist·(1+0.18·sin(k·angle))/r)^0.85` (spires, not domes; Gaussian bumps read as
  bubbles), a pass left open, faded out where the sea starts.
- **Where it meets another ground** (the desert's hfrag): sink the new terrain 1.5 m under it
  wherever they overlap and use **the same sand texture at the same tiling** - a different tint or
  scale shows a straight seam.
- Big flat cells look like squares in the engine: shade **smooth everywhere** (faceted rock on a
  24 m grid reads as checkerboard).
- Dunes on the plain: low-amplitude sines, faded to 0 at the plain's edge; guard with a custom prop
  (`terrain["dunes"]`) so re-runs don't stack them.

## Painting the ground (Vertex Paint mask)

- One material, one color attribute `Mask` (FLOAT_COLOR, POINT): **R = rock, B = grey rock,
  G = darker, A < 1 = meadow** (meadow amount `clamp((1-A)·2.5)`, so one stroke is enough).
- Textures **box-projected** in object space (no stretching on slopes), each mixed with itself at a
  second scale and rotation, plus a ~600 m soft macro variation: no visible tiling.
- Initial mask procedural (slope + height + noise, grey bands rising with height), then the user
  refines. Brushes: `Roccia`, `Sabbia` (paint R), `… chiazze` (3D cloud texture), `Roccia grigia`
  /`Roccia terra` (B add/sub), `Scurisci`/`Schiarisci` (G), `Prato`/`Prato pieno`/`Togli prato`
  (`ERASE_ALPHA`/`ADD_ALPHA`, strength 1), `Sfuma` (BLUR).
- **Brush traps (Blender 5.x):** `unified_paint_settings.use_unified_color/size` must be **off** or
  every brush paints the same color; size is `unprojected_size` (diameter) with
  `use_locked_size = 'SCENE'` for meters; texture map modes are `VIEW_PLANE/TILED/3D/...`;
  `vertex_paint.brush` is read-only (the user picks it); mark brushes as assets so they show in
  "Current File".

## Scatter brushes (Weight Paint → Geometry Nodes)

- One vertex group per kind on the terrain (`Rocce`, `Massi`, `Erba`, `Erba alta`, `Case`,
  `Palme`, `Latifoglie`, `Bosco`), one object `Sparsi <kind>` with a GN tree:
  Object Info(terrain, Relative) → Distribute Points on Faces (density, selection = attribute) →
  keep points where `random < weight` (painted weight = density) → Instance on Points (Collection
  Info, separate + reset children, pick instance, random index) → random Z turn (+ slight tilt for
  rocks) and scale → Realize Instances (muted at export).
- `FunctionNodeRandomValue` outputs by index: 0 vector, **1 float**, 2 int, 3 bool - `outputs["Value"]`
  is the vector one.
- A "Bosco" (woods) brush joins several chains (trees, tall grass, grass, boulders) on one weight.
- Kits are collections under `Kit` (outside the exported collection). Pieces: origin at the bottom
  center, real scale, a `Color` attribute at 0.5 if the game material multiplies by vertex color
  (otherwise they render black).
- Check the evaluated face count before export: a few painted patches reached **19 M faces**.

## Export: instances, not one mesh

- **Scatter → placements**: mute Realize, read `depsgraph.object_instances` of each `Sparsi` object,
  write per kit `<kit>_placements.json` (piece, location of the piece's bottom center, yaw, size with
  the long side first) and each kit piece once as a glb. The engine spawns them as instanced meshes
  (UE: HISM), grass with no collision/shadows, trees and rocks with collision.
- Terrain alone (vertex colors exported: `export_vertex_color="ACTIVE"`), the rest (town, props,
  tunnel, sign) as one level split in parts of ≤ 64 materials (Nanite) with see-through materials apart.
- **Foliage and decimated AI models break under Nanite** (cards shredded, shards in the air): import
  painted kits without Nanite; as instances they are cheap anyway.
- Never decimate thin AI models hard (grass 3800 → 180 faces became shards): ask the generator for
  the budget (see `tripo-3d-assets`), or keep ≥ ~700 faces for tufts.

## Matching terrain material in Unreal (Python)

Triplanar by hand (no material function): world position masked to XY/XZ/YZ, divided by size (cm),
three samples weighted by `normal²/sum`, per texture at two scales; lerp sand→rock by VC.R,
rock→grey by VC.B, darken by VC.G, meadow by `saturate((1-VC.A)·2.5)`, × a 600 m desaturated macro
sample (softened), then `Desaturation` ~0.15 to sit with the game's palette. Assign it to every slot
of the terrain mesh after import.

## Procedural content that worked

- **Town in a sculpted valley** (`faraway.py`): heights by rays on the terrain (sculpting moves
  vertices sideways, it is no longer a grid), main street along the valley's lowest line, parallel
  and cross streets, lots on both sides with an occupancy grid (shrink the footprint 3 m or every lot
  collides with its own street), houses with stone base following the slope, plaster walls, pitched or
  flat roofs, door, windows; then props cut from the game (chimneys, signs, awnings, lamps) with their
  **vertex colors** (the game's baked light) carried over.
- **Game props from merged level meshes**: a ripped level holds every copy of a prop in one mesh per
  material - split loose parts (numpy union-find on edges), merge parts whose boxes overlap across
  source objects (trunk + limbs + fruit = one tree), keep a few as templates. Build boxes first and
  copy faces only for the kept pieces (huge grass meshes otherwise).
- **Slum houses are façades only** (modules touching in rows, no back): cutting them out gives open
  shells - build closed houses with the game's textures instead.
- **Rock formations** from shards: let the user put the 3D cursor on one and take every shard within
  ~100 m (automatic clustering chains them into km-long groups).
- **Tunnel**: straight bore with a vaulted section, floor ramping between both portals, stone frames,
  terrain faces in the way removed; store the portal heights (re-runs find the ground already opened).
- **Hollywood-style sign**: text curves converted to mesh, stood up and turned to the town, each
  letter on the slope; check the reading direction from the town (letters came out mirrored once).

## Checking the map (QA)

- `haven_holes.py`: a downward ray per 6 m cell over the city ± 300 m classifies city floor,
  terrain, allowed water (bay, open sea), **HOLE** (water or nothing inside the city), **VOID**,
  **DROP** (city floor > 6 m above a wet neighbor: street ending in the air); writes a colored top
  view and with `--fix` adds slabs at the surrounding floor height and skirt walls down to the water.
- Verify in game with timed screenshots and a teleport option (`-JakTeleport=x,y,z@sec`,
  `-JakShotTimes=...`); don't trust a Blender view for fog, materials or Nanite.

## Working with the user

- Show screenshots of every step (Blender `look` from 2-3 angles, or game shots).
- Ask for a 3D-cursor click when a place can't be found by analysis.
- Long imports run detached and logged; tell the user the time left and which step it is on.
