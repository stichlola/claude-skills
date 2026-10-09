---
name: tripo-3d-assets
description: How to make game-ready 3D models with the Tripo API (tripo3d.ai) cheaply and cleanly - text/image to 3D, low-poly face budgets asked up front, sheets of many parts in one generation cut apart in Blender, P1 low-poly + texture from a user's image, concept pictures before characters, PBR for Unreal, costs, prompts and the failures already met. Use whenever a task generates, retextures or prepares 3D assets with Tripo, or plans a set of game props, characters or kit pieces.
---

# Tripo 3D assets: what works

Lessons from making ~150 models for a top-down toy-diorama game (QuestBoard) and its Unreal sibling.
Follow them unless the user asks otherwise; they save credits and re-dos.

## Hard rules

- **The key** lives only in the `TRIPO_API_KEY` environment variable. Never print it, log it, put it in a
  file or ask the user to paste it in chat. Send it only to `https://openapi.tripo3d.ai`.
- **No trademarked names in prompts** (e.g. D&D/WotC monster names, brand characters): describe the
  thing generically ("a small fire-breathing red dragon", not a product name).
- **Check the balance before every paid call** and stop if a task would pass the budget the user gave.
  A create call is never retried automatically (a reset must not pay twice); reads (task status) are.
- **Log every task** (name → task id, prompt, face limit, credits) in a committed JSON file. A paid task
  whose download failed is resumed from its id, never bought again.
- **Long jobs run in the background**; show the user the previews (Tripo's `rendered_image_url`, or a
  Blender contact sheet) when they are done.

## The single most important trick: ask for the face count up front

Pass `smart_low_poly: true` and `face_limit: N` in the generation request. Tripo retopologises the
model itself into clean low-poly. **Never simplify (decimate) afterwards**: it tore holes in models,
basins and leaves fell apart. If a shape breaks at a low count, ask for more faces, don't decimate.

Budgets that worked (top-down game, many copies on screen):

| What | Faces |
|---|---|
| Small props, grass clumps, flowers | 500 (Tripo's floor for text→3D) |
| Thin layered shapes (pine needles, bushes, leaves) | 600-800 (at 500 they came back as loose sheets) |
| Trees | 800-1000 |
| Furniture, chests, altars, braziers | 800-1200 |
| Houses, towers, barns, statues | 1200-2000 |
| One-of-a-kind centrepieces (fountains) | 2000-2500 (a basin fell apart at 1500) |
| Characters / monsters (also for Unreal) | ~10000 |
| A sheet of many parts | 3000-5000 for the whole sheet (~400 a piece) |

The price does **not** change with the face count, so a sheet of 12 parts costs the same as one prop.

## Pick the route

1. **Scenery prop, quick**: text → 3D directly, one shared style suffix for the whole set
   (`/generation/text-to-model`, `texture: true`, `texture_quality: "detailed"`, `pbr: false`,
   `smart_low_poly`, `face_limit`, plus a `negative_prompt`). ~40 credits. Show previews afterwards.
2. **Characters**: first **2 concept pictures** (`/generation/text-to-image`, 5 credits each), show
   them to the user, convert **only the chosen one** (`/generation/image-to-model` with
   `input: <image task id>`, `texture_quality: "detailed"`, `pbr: true` if it goes to Unreal too).
   ~50 credits. Pose in a relaxed T-pose for rigging, empty hands, no base.
3. **Many small parts → a sheet** (the cheap way, see below): one picture with 5-12 pieces, one
   image→3D, Blender splits it. ~55 credits for the lot, ~5 a piece instead of ~40-50.
4. **From the user's own image, low-poly**: upload the image (`POST /files`, multipart, returns a
   `file_token`), then `/generation/image-to-model` with `"model": "P1-20260311"`,
   `face_limit` (P1 takes 50-20000; `P2-20260801` takes 48-50000 and makes quads), `texture: false`;
   then texture it with `/models/texture` (`input: <mesh task id>`, `texture_prompt: {image:
   {file_token}}`, `texture_quality: "detailed"`, `pbr: true`). P1 mesh ~40 + texture ~20 credits.
5. **Modular kits (walls, roofs)**: one "master" strip per material at true size, Blender cuts the
   pieces. Works for clean repeating materials; **failed for whole house kits** (roof broken, door too
   short). For architecture, prefer modelling the pieces in Blender (booleans for openings) and using
   Tripo only for textures.

Costs seen (credits, 100 = 1 USD): text→image 5, text→3D 40, image→3D with PBR 50, P1 mesh 40,
texture 20. Always read `credits_consumed` from the finished task and stop if it is above the estimate.

## Prompts

- Subject first (shapes, materials, colours, proportions in cm or tiles), then pose, then the **shared
  style string** so the set looks like one toy line. Keep text→3D prompts under 1024 chars, image
  prompts under 1800.
- Say what you don't want: "single object, no ground plane, no base, no pedestal, no characters, no
  text". Text→3D takes a `negative_prompt`; text→image reads negatives after `--no`. **Image→3D has no
  negative prompt**: the picture itself must not contain the unwanted thing.
- **Draw it, don't describe it** for anything with exact proportions (doors, wall pieces): picture
  first, check it, then image→3D. Text→3D gave fences instead of walls and huts of 256 loose pieces.
- **Test with a body**: anything a figure passes through must fit the tallest figure (door ≥ 1.15 ×
  hero height). Check it in a Blender contact sheet with a figure next to it.
- Stone/metal parts in a **neutral pale stone** so the game can tint them (bronze, gold, basalt).

## Sheets of parts (the cheap way)

1. Picture prompt: "Game asset sheet: the separate pieces laid out on an even grid with wide empty
   gaps between them, none touching another, each whole, seen from a three-quarter front view, plain
   light grey background, soft even studio light, <style>. No shared base, no table, no ground, no
   shadows between pieces. No text, no labels, no numbers, no measurements, no arrows." then the list
   row by row ("Top row: ..., Middle row: ..., Bottom row: ...").
2. A bad picture? Make **one** more take (5 credits) before paying for 3D.
3. Image→3D the chosen picture with `face_limit` 3000-5000, `texture_quality: "detailed"`, `pbr: true`.
4. Split in Blender (`reference/blender-sheets.md`): weld by position, find loose shells, give each
   shell to the piece whose centre (measured on the front view) is nearest, so a split boulder's two
   halves or three gems stay one piece. Trees: drop any stand/plug, cut crown from trunk where the
   foliage starts, give hanging strands far from the trunk axis to the crown.
5. Each piece: origin at the middle of its foot, front to the game's front, scaled to its true size
   (1 = one tile). Export one GLB with one texture per sheet (the sheet is the atlas), WebP textures,
   then `gltfpack -cc -kn -km -ke -vp 12` (meshopt + quantisation; the loader needs the meshopt decoder).
6. Keep a manifest (piece → sheet, size, top point for stacking) and a test that the code's list,
   the JSON and the GLB name the same pieces.

## In the engine

- Load each GLB once; draw repeated props **instanced** (one draw call per model per material).
- Share materials between copies; don't dispose cached materials when a scene rebuilds.
- For Unreal keep Tripo's raw PBR files (before gltfpack); the web build gets the compressed ones.

## Files

- `scripts/tripo_client.py` - a small, dependency-free client: balance, text→image, text→3D,
  image→3D (task or uploaded file), P1, texture, wait, download, task log, budget guard.
- `reference/api.md` - endpoints and request bodies.
- `reference/blender-sheets.md` - splitting a sheet into pieces, with the bmesh code.
