---
name: game-art-review-loop
description: An automated improve-and-review loop for game environment art (set dressing, junctions between levels, rubble, colour matching) - deterministic in-game captures from fixed review points in one boot, separate AI reviewers (a brutal AAA art director that scores, a technical QA tester that lists defects with pixel boxes, an automation engineer that reads the code), a defect locator that maps pixel boxes to scene objects through the game camera, an autofix pass, screenshot regression diffs, physics-settled rubble made from the geometry that was cut away, and the traps met (vis culling, UV precision, vertex-colour colour space, collision moving the camera). Use when the user wants a scene, a level junction or set dressing improved by iterating with agent reviews and scores, or asks to automate visual QA of a game level.
---

# Game art review loop

From a Jak 3 fan remaster (OpenGOAL + Blender): the Jak 2 palace plaza brought into Jak 3's Haven
City through two passages cut in the ruins. The user asked for rounds judged by separate agents,
stopping at a score >= 8 or after N rounds. Ten rounds taught what follows.

## The loop (one command per round)

1. **Fix** - an automatic pass on the previous round's defect files, then a short hand-written step
   for what needs reasoning (`autofix.py`, `iterN.py`).
2. **Build** - collision, export, level build.
3. **Capture** - all review points in ONE game boot: the game walks the points by itself (an env var
   turns it on) and logs `[review] ready <point>`; a script watching the log captures the window and
   the game camera. 5 shots in ~95 s instead of a boot per shot (~40 s each). Run the walkway probe
   (sphere sweeps along the paths: WALL / HOLE / DROP) in the same boot.
4. **Regression diff** against the previous round: changed-pixel share per shot and a diff image;
   >55 % changed = the view moved (flag it before any reviewer sees it).
5. **Review** - in parallel, the same agents every round (resume them, don't respawn: they keep
   their standards and remember what they asked for):
   - **AAA art director**: scores (A: colour/material continuity, B: rubble realism + no void) and
     lists problems; brutal, "8 = passes an AAA remaster review".
   - **Technical QA**: no scores, only defects, one per line, in a fixed machine-readable form:
     `- [shot] (x1,y1)-(x2,y2) [CATEGORY] [SEVERITY] object: what is wrong. Fix: ...`
     (FLOATING, INTERPENETRATION, VOID, TEXTURE, PALETTE, SEAM, CAMERA, LAYOUT). Both write their
     lines to a file in the round's folder.
   - **Automation engineer** (every few rounds): reads the placement code and the reports, answers
     with root causes per defect class and a prioritized list of code changes. Its quick wins were
     the biggest step up in quality.
   Tell reviewers what changed, against their own list, and what is original game geometry (so it is
   not counted every round).
6. Stop at the target score or the round limit; report scores per round to the user.

## Turning reviewer pixels into fixes

- **Log the game camera at capture time** (position, forward, fov) - then a pixel box becomes a set
  of rays. The locator casts a 7x7 grid (15x15 for thin boxes: rods, sticks) through each box against
  what the game draws (skip collision-only meshes; emulate any engine-side cut volumes), and returns
  the objects hit, their distance, and the share of rays that hit nothing (void).
- **Autofix by category**: FLOATING/INTERPENETRATION/CAMERA/LAYOUT on generated pieces -> remove;
  PALETTE/TEXTURE -> re-texture; VOID -> a plug slab at the depth the box's other rays reach. Anything
  on original geometry is only reported.
- **Verify the locator once** by rendering the DCC scene from the logged game camera and comparing
  with the screenshot: when they differ, the engine is hiding or showing something the DCC isn't
  (see traps) - that difference is itself the bug.

## Placement that survives review

- Hand-written placement rules (support tests, push-out from walls, overlap thresholds) produced
  most defects: cantilevers, slabs inside walls, one-point contacts, pieces sunk in slopes. Each
  strict rule fixed one class and created another (a strict support test removed 1800 pieces and the
  passages looked "built, not collapsed").
- **Physics settle instead**: Bullet rigid bodies (convex hulls) dropped from 2-4 m with a random
  turn against a passive collider made of the drawn geometry around the spot, 150 frames, apply the
  visual transform, remove the physics; drop pieces that fell into the void, travelled far or ended
  in a walkway. Run it headless (`blender -b`), per region.
- **Make the rubble from what was cut away**: take the faces crossing the cut volume (big triangles
  rarely have their centre inside - clip them with the volume's planes, `bisect_plane` with
  `clear_outer`), split into Voronoi chunks, give them thickness - debris then has the wall's own
  textures and baked light, so it belongs.
- Rubble is structure, not scatter: hero slab against a wall, mid pieces fanned at its foot, small
  bits thinning out. Lone pieces and thin rods always read as "procedural" - remove them.
- Keep walkways explicit (segments + half width) and narrow enough that their edges can take rubble.
- Keep review spawns and camera booms clear of collision: a collision box near a spawn launched the
  player and pushed the camera, and two rounds were scored blind.

## Traps met

- **Engine visibility culling**: a level seen from a place the original game never allowed (inside
  the new area) had walls culled by its precomputed visibility: reviewers saw "debris floating in the
  sky" that was the level's own geometry. Turn the culling off for those levels near the new area.
- **UV precision**: the level builder stored UVs coarsely: world-planar UVs (hundreds of tiles)
  rendered as one flat colour. Do NOT fix it by shifting each face by whole tiles: the builder welds
  vertices by position, the UV jumps between faces became stretched streaks. Generate UVs small and
  continuous at the source (planar/box from the mesh's own minimum corner); keep a per-mesh shift at
  export only as a guard, never touching clamped textures near 0.
- **Grade per texture, not per level**: a whole-level grade (desaturate + tint in the shader) to make
  the imported area match also dulled the surfaces borrowed from the host game into flat dark grey.
  Bake the grade into the imported area's own textures at export, leave the shader neutral.
- **Some textures just don't survive** the custom-level path (a borrowed pavement stayed flat with
  correct UVs): after two attempts, swap to a material that renders and move on.
- **Physics leftovers**: after a settle, some pieces fall out of the world (hundreds of metres down)
  and inflate the level's collision grid (the file doubled). Check "nothing below / far under the
  map" by casting DOWN from the piece; casting from above hits roofs and deletes good pieces under
  overhangs. Removing pieces for being "lone" after a settle emptied the passages: keep what settled.
- **The camera that matters is the logged one**: the game camera settles somewhere else than the
  continue point's camera; collision near the real one moves the view between rounds. The regression
  diff flags it (>55 % changed); then compare content, or re-baseline and tell the reviewers.
- **Vertex colours are baked light**: generated meshes need the same linear mean as the floor
  (byte colours are sRGB; set and read in linear), and the attribute must be the active/render one,
  or the pieces render black.
- **Memory budget**: the new area lives in a borrowed heap slot; collision of generated pieces as
  oriented boxes (12 triangles) on the solid pieces only, biggest first, under a triangle budget.
- **DCC vs game**: a DCC render is a fast inner loop, the game capture is the truth (fog, culling,
  texture handling differ).

## When the scores plateau

In the Jak run the scores went 3/2, 5/3, 6/5 in three rounds, then stayed at 5-6 / 4-5 for seven
more rounds while the defect lists changed every round. What that taught:

- **A fix often moves the defect instead of closing it**: a gap closed by a wall reappeared beside
  the wall; a plate that covered a void became "a straight raised ledge across the lane". Ask the
  reviewers whether a defect is *new* or *moved*, and close gaps with overlap (0.5 m into the
  neighbour, floor to top), never edge to edge.
- **Global changes cost a round each**: a palette or texture change shifts every shot, the director
  re-reads the whole scene and the score dips (round 7-8) before it recovers. Change one global
  thing per round, and keep it as a parameter (env var) so it can be tuned without re-placing.
- **Generated surfaces need a broken edge**: every straight, clean boundary (plate vs floor, skin
  patch on a grid, wall top) got flagged until it was jagged, sunk in or covered by debris.
- **Texture by role**: a slab in the floor texture placed high reads as "floor stuck to the
  ceiling" - wall pieces take wall stone, floor pieces floor stone.
- After ~3 rounds without a score change, stop polishing pieces: ask the director for the 3 fixes
  that would gain most (it gives them), or tell the user the approach needs hand work.

## Working with the user

- Report scores per round in a small table; say plainly when a round regressed and why.
- Each round builds on the previous one: never regenerate everything from scratch unless the
  reviewers' list says the approach is wrong.
- Long Blender jobs: headless, in the background, with a wait that notifies (the MCP call times out
  while Blender keeps working).
