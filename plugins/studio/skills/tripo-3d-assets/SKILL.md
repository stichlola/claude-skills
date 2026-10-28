---
name: tripo-3d-assets
description: How to make game-ready 3D models with the Tripo API (tripo3d.ai) cheaply and cleanly - text/image to 3D, low-poly face budgets asked up front, sheets of many parts in one generation cut apart in Blender, P1 low-poly + texture from a user's image, concept pictures before characters, PBR for Unreal, animating non-human creatures from generated video, costs, prompts and the failures already met. Use whenever a task generates, retextures or prepares 3D assets with Tripo, or plans a set of game props, characters or kit pieces.
---

# Tripo 3D assets: what works

Lessons from making ~150 models for a top-down toy-diorama game (QuestBoard) and its Unreal sibling.
Follow them unless the user asks otherwise; they save credits and re-dos.

## Hard rules

- **The key** lives only in the `TRIPO_API_KEY` environment variable. Never print it, log it, put it in a
  file or ask the user to paste it in chat. Send it only to `https://openapi.tripo3d.ai`.
- **No trademarked names in prompts** (e.g. D&D/WotC monster names, brand characters): describe the
  thing generically ("a small fire-breathing red dragon", not a product name).
- **Ask before spending.** Before any paid call (an image ~5, a model ~40), stop, show the user what will be
  generated (reference, prompt) and the cost, and wait for an explicit yes; one yes covers only the
  generation it was given for. Free steps (balance, Blender cutting, placing, importing) go ahead.
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

## How many pieces in one generation: by how close they are seen

A sheet is one model: its `face_limit` and its one texture (2048 x 2048 from image→3D) are **shared**
by the pieces. Per piece, roughly:

| Pieces | Texture each | Faces each at a 20000 limit |
|---|---|---|
| 1 | 2048² | 20000 |
| 2 | ~1450² | ~10000 |
| 4 | ~1024² | ~5000 |
| 8 | ~512² | ~2500 (at an 8000 limit: ~1000-2000) |

- **Seen from mid or far** (rocks, pebbles, props, houses from the street, a top-down game): sheets of
  6-12, the price does not change with the count. This is where sheets pay.
- **Seen up close** (grass at the player's feet, a hero prop, anything the camera can reach): **1-2
  pieces** per generation with a high `face_limit` (10000-20000) and `texture_quality: "detailed"`.
  A sheet of 8 desert grass tufts (8000 faces, one 2K texture) looked like blurry crystals at 1 m.
- If the engine draws copies instanced with a distance swap to a cheap version (the game's own model
  or a low LOD), high face counts near the camera cost little: budget for the close view.
- **Thin blades and leaves: `smart_low_poly: false`** for close-up pieces. Low-poly mode rebuilds each
  blade as a chunky 4-5 sided prism; without it Tripo reduces its detailed mesh to the `face_limit`
  and blades stay thin strips. Keep low-poly mode for solid, chunky shapes.
- Variety without more credits: one or two detailed pieces, then the variants in Blender (copies
  merged and offset, a wedge of blades removed, squashed or stretched), plus a random scale and tilt
  per copy in the engine.

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

## Redoing a game's own props from screenshots (remakes)

Used to replace a PS2 game's low-poly rocks, trees and grass in Unreal (jak3-ue5); ~45 credits a kind.

1. **Reference**: a clean in-game screenshot of the original prop, cropped tight (no character in it,
   no HUD), upscaled to ~1000 px. It need not be sharp: style and colours carry over.
2. **Picture from the reference** with `POST /generation/image-to-image` (`file: {type, file_token}` of
   the uploaded crop + a prompt saying *how to change it*: "Redesign the ... of the reference image as a
   sheet of N separate ...: keep the same colours and shapes, but more detailed: eroded edges, cracks,
   strata ...", then the sheet layout and "plain light gray background, no base, no shadows, no text").
   Show it before paying for the 3D. Ask for "all different" variants explicitly: one sheet came back
   as three near-identical pairs, another (thin trunks) as six copies of the same trunk.
3. **Image→3D** as for any sheet. Expect losses: Tripo rebuilt **4 of 8** pine tufts and 4 of 6
   boulders (the far rows went missing); plan sheets with spare pieces. Thin blades of grass and thin
   trunks did come through (8/8, 6/6) at `face_limit` 4000-8000.
4. **Cut** with the sheet splitter. The sheet's rows do not always come back along Z: one model laid them
   out **in depth** (rows along X, columns along Y). Pick the axis with the widest spread of shell
   centres for the columns and, of the other two, the wider one for the rows, then k-means from the grid.
5. **Place** the pieces where the original props were: find the original pieces in the level mesh
   (connected triangles of one material, welded by position), fit each piece to the original's bounds
   (long side along the original's principal axis, plus a random half-turn and a few degrees, ±10 %
   size), and either lay it over the original (a bit bigger) or **take the original's triangles out of
   the level mesh** (cleaner; the game's separate collision mesh stays). Grass cards cross each other:
   merge pieces whose centres are within ~1.5 m first, or every card gets its own tuft.
6. **Tint in the engine**, not with a new generation: Tripo's sandstone came out orange; a material
   colour factor (e.g. ×0.36/0.38/0.42 RGB) fixed it for free.

7. **Many variants from few pieces**: rocks and pebbles are small on screen, so 9 stones on one
   3x3 sheet beat one stone per generation. Cut them, then build variants in Blender by copying pieces
   of the **same sheet** (they share one texture, so a heap of different stones stays one material):
   random yaw, small tilt, ±size, flattened (x1.3 wide, x0.55 tall), pairs, heaps, scatters.
   A "layered slab" prompt gave wooden planks and bread twice; what worked: "built of three or four
   stacked horizontal rock layers, each layer's edge sticking out a little over the one below,
   darker shadowed groove under each". Bring the result to the scene's colour by a target average
   (tint = target / texture average) rather than the texture's own: the raw sandstone read white.

A **tileable texture** works too (picture only, 5 credits): image-to-image from the current texture,
"seamless tileable top-down texture ... seen straight from above". It still came back in perspective
(blurred far edge): crop the sharp, even part and make it tile yourself (blend the crop with itself
shifted by half, the shifted copy taking over toward the edges).

**Errors seen**: an image-to-image task "failed, 1001 Failed to generate image" with a 1 MB PNG
reference charged nothing; the same reference as a ~130 KB 768 px JPEG (`type: "jpeg"`) worked.

## Budgets by role, and the checks after generation

- Give every piece a role and send `face_limit = pieces × budget(role)`: grass/reeds 500, small prop
  1500, rock 2000, tree/house 4000, big rock formation 5000, vehicle 8000, character 10000. Show the
  budget with the picture before paying for the 3D. Never fix the count afterwards by heavy
  decimation: grass tufts cut from 3800 to 180 faces turned into floating shards.
- Tripo can return more faces than asked (3000 → 5000 seen) and models **facing backwards**: check
  the count, look at each model from 4 sides and turn it, set real-world size and collision.
- Batches: one manifest file (every prop with its pictures and settings), several tasks in parallel,
  resume from the task log so nothing is paid twice. Front/side/back pictures give truer models.
  Two text-to-image tasks at once already met `HTTP 429 "You have exceeded the limit of generation"`: no
  task is made and nothing is charged, so wait (`Retry-After`, else ~15 s) and send the create again.
- UI art (game menus' parchment, wooden buttons, plaques) as text-to-image pieces on white, cut out and
  nine-sliced, was turned down: painted pieces with thick rims and ornate ends look wrong once stretched to
  small, varied button sizes. (A scripted hand-drawn skin went too; the user kept the plain website UI.)
  Show one piece in the real UI before generating a whole kit.
- Tripo Studio (the website) credits are cheaper and often discounted but are a separate balance from
  the API: hero assets can be made there by hand and handed to the agent as `.glb`.
- Architecture (walls, modular buildings) comes out better built in Blender by script with
  AI-generated tileable textures (offset by half and blend the seams; dirt = what the AI picture
  has darker than the clean wall); keep Tripo for small detailed props. Tripo pieces float off walls
  and bake everything into one texture.

## Gameplay details seen in the same videos (Godot + agent)

- Physics: Jolt (built into Godot 4) for breakables - glass cut around the hit point, pieces thrown
  along the shot; shelves where one falling bottle knocks the next.
- Many enemies: one flow field (arrows to the player, around walls and up stairs) for hundreds;
  for a few dozen better-looking ones, each its own brain with flanking (come from different sides).
- Insect walk in code: two leg groups (tripod gait), feet planted never slide, a step starts after
  half a step of body travel, so faster bugs take longer strides.
- Doors opened with the player's hands feel real; sliding by themselves feels fake.

## Animating creatures with unusual bodies

Bipeds: clips written in code onto one shared skeleton. Quadrupeds, dragons and monsters have no motion data;
the route that worked in a published experiment (not yet tried in QuestBoard) is:
- a skeleton from UniRig, several tries checked against the mesh;
- a generated video with **two cameras in one picture** (front and side), so each joint is triangulated;
- a joint detector (DINO) fine-tuned on ~3000 renders of the creature itself, once per creature;
- an **exam on a made-up motion** before paying for any video.

Point tracking, SAM 2, single-view depth, animal pose models and painted legs all failed.
Details: `reference/creature-animation.md`.

## In the engine

- Load each GLB once; draw repeated props **instanced** (one draw call per model per material).
- Share materials between copies; don't dispose cached materials when a scene rebuilds.
- For Unreal keep Tripo's raw PBR files (before gltfpack); the web build gets the compressed ones.

## Files

- `scripts/tripo_client.py` - a small, dependency-free client: balance, text→image, text→3D,
  image→3D (task or uploaded file), P1, texture, wait, download, task log, budget guard.
- `reference/api.md` - endpoints and request bodies.
- `reference/blender-sheets.md` - splitting a sheet into pieces, with the bmesh code.
- `reference/creature-animation.md` - animating non-human creatures from generated two-camera video: the pipeline, the exam, what failed.

- Two generations at once on the same key can fail with HTTP 429: run batches one after another.
- Image-to-image redraws do not keep positions: anything that must line up with game data (map
  icons, borders) has to be checked after, and masks computed on the original won't fit; crop
  bands measured on Tripo's own picture instead. Empty placeholder inputs make Tripo invent content:
  generate those procedurally.
