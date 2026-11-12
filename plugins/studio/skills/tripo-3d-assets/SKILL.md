---
name: tripo-3d-assets
description: How to make game-ready 3D models with the Tripo API (tripo3d.ai) cheaply and cleanly - text/image to 3D, low-poly face budgets asked up front, sheets of many parts in one generation cut apart in Blender, P1 low-poly + texture from a user's image, concept pictures before characters, PBR for Unreal, picking routes by use (code, Blender, sheets of 4 with texture steps, one hero picture), cleanup of stray faces and black triangles, PBR derived from the colour texture, animating non-human creatures from generated video, costs, prompts and the failures already met. Use whenever a task generates, retextures or prepares 3D assets with Tripo, or plans a set of game props, characters or kit pieces.
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

## Choosing how to make each object (routes, texture steps, shared rules)

Decided with the user after a round of sheets in Nov 2026. Start cheap, upgrade only what still looks
soft **in the game**, seen from the game camera.

**Pick what is worth doing first by counting use.** Generate many maps with the game's own generator
(e.g. 6 seeds x every recipe), count props per id and in how many maps each appears. The top ten are
usually small dungeon/storage dressing (rubble, skulls, busts, columns, torches, crates, barrels,
coins). Many of them are code-made blocks, and those gain the most from a real model.

Routes (credits, 100 = 1 USD):

| Route | Shape | Texture | Credits / object | Use for |
|---|---|---|---|---|
| A. Code | simple shapes in the game's code | colours in code | 0 | tiny things repeated hundreds of times (coins, bones, pebbles) |
| B. Blender | modelled or procedural, exact sizes | projected from the user's picture or painted procedurally | 0 (time, needs Blender) | pieces that must join: walls, bridges, fences, floors |
| C. Sheet of 4 | Tripo image->3D of one picture with 4 objects | see steps C1-C3 | ~12 | the normal route for most props |
| D. One object, one picture | Tripo image->3D of a large single-object picture | Tripo's, full resolution | ~50 | a few hero objects (hut, statue, well) |

Text->3D (~40) was dropped as a default: it costs almost as much as D and gives less control of style.

Texture steps for route C:

| Step | What | Extra / object | Result |
|---|---|---|---|
| C1 | Tripo's texture + Real-ESRGAN + procedural touch-up (warm top light, dark crevices, light edges, colour grade) | 0 | fine from above, soft up close |
| C2 | Tripo re-textures the whole sheet model (`/models/texture`) from the same picture upscaled to 4096 | ~5 (20 a sheet) | sharper |
| C3 | Each object cropped, upscaled and re-textured alone | ~20 | as sharp as route D (needs the split piece uploaded as a model: verify the API first) |

Shared rules:

- **Pictures:** the user makes them (e.g. with Gemini) and sends them as **files**. Images pasted inline
  in chat may arrive downscaled (~1024) or not as files at all. Below 2048, upscale x4 with Real-ESRGAN
  first. White background, objects well apart, same 3/4 top view, one family and similar size per
  sheet, at most 4 objects.
- **The sheet divides the detail, not the texture.** Tripo's texture is 4096 either way, but it is
  painted from the picture: 4 objects in a 1024 picture leave ~250-500 source px each, stretched over
  the model, so they look blurred up close. More source pixels per object (big picture, or one object
  per picture, or C2/C3) is the only real fix. Real-ESRGAN on the finished 4096 atlas (downscale to
  1024, x4 back) helps only a little.
- **To re-texture, keep the shapes.** A new picture for C2/C3 must have the objects in the same place
  and shape as the one the model came from, so upscale the same sheet; never regenerate it.
- **Face budgets asked up front** (`smart_low_poly`, `face_limit`): 300-500 for things repeated
  hundreds of times (1600-2000 for a sheet of 4), 800-1200 for props in view, 2000-4000 for big
  pieces. `face_limit` counts quads: 2400 came back as ~4500 triangles, so roughly double it in
  triangles.
- **Cleanup after every generation** (trimesh is enough, no Blender needed):
  - Weld, split into connected parts, delete strays under ~10 triangles. A 3-triangle stray rendered
    as a **black triangle**.
  - Give small real parts (clover leaves) to the nearest big piece. Split the objects.
  - A sheet comes back as a slightly tilted scene: put each piece's base on y = 0, upright, centred,
    scaled to the grid (a wall cap exactly 1 x 1 square).
  - Fix inconsistent winding (seen on plants).
  - Check boundary edges (holes) and non-manifold edges.
- **Materials:**
  - Tripo GLBs come with `doubleSided: true`, so inside-out strays show their unlit back face as
    black. Make them single-sided (plants double-sided only if thin leaves vanish, and only with
    consistent normals).
  - Tripo sets `metallicFactor: 1` with a metallicRoughness map. Without an environment map that
    makes stone dark and brown. Set **metal 0**.
- **PBR from the colour texture** (procedural, free):
  - luminance minus low-frequency shading = height;
  - normal map from its Sobel gradient;
  - AO/cavity from the dark crevices;
  - roughness = inverted, slightly contrasted brightness, clamped to the toy look (stone ~0.75-0.95,
    leaves ~0.6-0.8);
  - keep Tripo's maps only if they look better side by side.
- **Web delivery:**
  - Textures at 1024 (2048 for big pieces) as WebP, one file per family.
  - The npm/node build of `gltfpack` has **no WebP/KTX** (use Blender or a native build), and its
    `-sa` aggressive simplify **destroys UVs**: never use it on textured models.
- **Review:** preview to the user before placing, then one shot in the real game from the top-down camera.

API notes confirmed in this round (v3):
- Upload a local picture with `POST /files` (multipart), which returns a `file_token`.
- Pass the token straight as `input` to `/generation/image-to-model`, with `model_version`, `texture`,
  `pbr`, `texture_quality: "detailed"`, `smart_low_poly`, `face_limit`.
- Credits are taken **when the task is created** (the balance dropped before the first task finished),
  so check the balance against the full cost before starting a second one.

**Other generators tried and dropped:** Hunyuan3D (LowPoly + PBR, through Higgsfield) gave good 4K
textures but ~10000 triangles whatever the mode, 20-29 MB of 4K PNGs, no face limit, and it could not
be reduced below ~3000 triangles without breaking the UVs. Not worth it for a web game.

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

Sharpness: every piece shares the picture's pixels, so with 5-12 pieces each texture is soft up close.
That is fine for tiny props seen from far; for props in view keep sheets to **4** and big pictures
(see "Choosing how to make each object").

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
