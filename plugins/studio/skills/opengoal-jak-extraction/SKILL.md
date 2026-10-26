---
name: opengoal-jak-extraction
description: Getting usable assets out of a Jak and Daxter / Jak 2 / Jak 3 disc with OpenGOAL for a fan remake in another engine - extractor options, what the glb ripper drops (align channel, low key rate, hfrag terrain), the desert height field from the .fr3, Wang-tile sand, sound banks to WAV, the streamed music in VAGWAD that the ripper skips (with its format), GOAL units and axes. Use when a task extracts, converts or rebuilds models, levels, terrain, animations, sounds or music from a Jak game, or debugs why an extracted asset looks or moves wrong.
---

# OpenGOAL extraction for Jak remakes

Learned rebuilding Jak 3 (PAL) in Unreal Engine 5 (jak3-ue5) with OpenGOAL v0.3.8. The user's own disc;
never commit game data (ISO, extracted files, textures, meshes, audio).

## Tools and units

- `extractor.exe [-g jak3] -f -e|-d <iso_data folder or .iso>`; options merge into the decompiler config
  with `--decomp-config-override '{"key": value}'` (keys in `decompiler/config/<game>/<game>_config.jsonc`:
  `rip_levels` → levels as `.glb`, `rip_collision` → `.obj`, `save_texture_pngs`, `rip_streamed_audio`,
  `process_tpages`, `levels_extract`...). For a one-off rip, turn off everything else (`process_tpages`,
  `levels_extract`, `extract_collision`, `process_game_text`, `find_functions`, `dump_objs`: false), a
  pass then takes ~2 minutes.
- The readable GOAL source of the game is in `data/goal_src/<game>/`: the real numbers (speeds, jump
  heights, camera, vehicle constants, attack timings) are there; read them instead of guessing.
- Units: 1 m = 4096 GOAL units; 65536 = 360°. GOAL is Y-up: world (x, y, z) → Unreal (x, z, y) × 100 cm
  (that is what the game's continue points and the ripped glb need, checked against spawn heights).

## What the glb ripper gets wrong

- **Only geo 0 (the most detailed LOD)** of tfrag/tie/shrub, merged per level per material: a level is
  one mesh up to 2 km across. Props (rocks, trees, grass cards) are just connected triangle groups of one
  material inside it: weld by position and union-find to get them back as pieces.
- **The align/prejoint animation channels are dropped.** Whatever the game moved through them is gone:
  the punch's forward lunge (re-do it as a velocity curve, ~3-5 m over 60 % of the clip with ground
  friction off), sidekicks sitting on Jak's shoulder (re-attach to `LshoulderPad` with the body's
  rotation), a smaller in-game scale for Daxter (~0.6).
- **Keys at ~15 per second.** A joint turning ~200° between two keys (the spin kick's `main` joint) is
  interpolated the short way (~160° backwards): a jerk. Fix at runtime: measure the joint's yaw in mesh
  space each tick and turn the mesh by whatever makes the body follow one smooth turn; the first jerk's
  sign is opposite to the real turn. Do not add a procedural spin on top: the turn is already in the
  bones (spread over the attack and its `-end` clip).
- **The hfrag terrain (Jak 3 desert dunes) is not exported at all.** It is in the level's `.fr3`
  (`data/out/<game>/fr3/<level>.fr3`: an 8-byte size, then zstd; tfrag3 format version 43): a 512 × 512
  grid, 8 m spacing from the world origin, found by shape (a u64 count, then 16-byte vertices
  `<f I H B B I` = height, vertex index, colour index, u, v, 0). Time-of-day colours follow (8 palettes ×
  RGBA, palettes 0-3 are daylight).
- **The hfrag's sand texture is a Wang atlas** (512 × 256, 16 × 8 tiles of 32 px; horizontal edges in 3
  colours, vertical in 4; column c → (left, right) = divmod(c % 8, 3), every pair but (2, 2); row r →
  top r // 2, bottom 2·(r % 2) + c // 8). Laid out as-is it shows a grid of seams: compose a periodic
  texture choosing tiles whose edges match, then re-tile it from soft random patches (each tile has a
  bright blob in the middle, so even a correct Wang layout shows a lattice).
- **No normals at all**: the engine shades every triangle flat and the PS2 geometry looks faceted ("low
  poly") where the game drew it smooth. Compute area-weighted corner normals, welded by position, that
  only average faces within ~55° (split vertices there so building corners stay sharp).
- **Every primitive references the level's whole shared vertex buffer.** Harmless for small levels, but
  Jak 3's Haven farms (thousands of instanced tie pieces) add up to over a billion vertex reads: the
  Unreal import asked for 87 GB and crashed. Give each primitive its own buffer with only the vertices
  its indices use (1.16 billion → 250 thousand).
- Haven City's districts are mostly **tie and shrub** (windows, beams, vines, wires: ~400k triangles a
  district); the tfrag holds only a few thousand. If a district looks bare, the low-detail backdrop
  (`ctywide`) is being shown instead of the district level, or the district failed to import.
- **Ocean heights differ per map**: the start-corner y of `*ocean-map-<name>*` (Jak 3: desert/wascity
  9 m, city 0 m, the city map is in `engine/gfx/ocean/ocean-tables.gc`). If levels are moved to share
  one world, each keeps its own sea at its own (moved) height.
- Continue points in `engine/level/level-info.gc` (`:trans`, GOAL units) are the reliable spawn points:
  a level's bounding-box centre is often out at sea.
- Level backdrops (e.g. `desert`) hold low-detail copies of areas shown in detail by other levels (a
  rock "cap" over the city, coarse mountains): cut them where the detailed levels are.

## Sounds and music

- **Sound effects**: `"rip_streamed_audio": true` writes every sound bank (`SBK/*.SBK`) to
  `decompiler_out/<game>/audio/sfx/<BANK>/<SOUND>.wav` (48 kHz stereo; looping sounds come out 10 s long)
  and the cutscene streams to `audio/voice_lines/<LANG>/`. On Windows it **stops** at a bank with a `*`
  in a sound name (`GUNGAME1`, `ONIN1`, `WASTOAD`): move that `.SBK` aside, re-run, move it back.
  Useful Jak 3 names: `COMMON/PUNCH`, `SPIN_KICK`, `GUN_PUNCH_HIT`, `JUMP`, `JUMP_DOUBLE`, `LAND_SAN`,
  `JAK_BOOT_RUN`, `HIT_BACK`, `EXPLOSION`; `COMMONJ/RED_SHOT_FIRE`; `BLOW1/HC_GUN_FIRE` (Hellcat gun);
  `CITYCARH/CAR_ENGINE_2`, `VEHICL_IGNITION`; `DESERT1/STORM_WIND`.
- **Music (Jak 3) is not in the sound banks** and the ripper skips it: it is streamed from
  `VAG/VAGWAD.INT`. `VAG/VAGDIR.AYB` = "VGWADDIR", u32 version 2, u32 count, then u64 entries: name in
  the low 42 bits as two 21-bit halves (high half first), each 4 characters base 38 (" A-Z0-9-"),
  6 flag bits, offset in 32 KiB blocks in the top 16 bits. Each stream: PS-ADPCM, the two channels
  interleaved in 0x2000-byte blocks, each channel's first block opening with a 0x30-byte "VAGp" header
  (little-endian data size and rate, 44100, "Stereo"). PS-ADPCM filters (0,0) (60,0) (115,−52)
  (98,−55) (122,−60): `s = (nibble << 12 >> shift) + (s1·f0 + s2·f1) >> 6` (mind the sign: add f1).
  Tracks: `DESERT`, `WASCITY`, `DESHOVER` (Hellcat), `WASCHASE`, `DESRALLY`... (`level-info.gc`
  `:music-bank` names the area's). Tracks hold all their variations: 5-13 minutes each.
- Check a decoder without listening: the mean level should be a few thousand, not ~30000 (saturated =
  wrong filter sign or misaligned blocks), and sample-to-sample jumps at block boundaries should be no
  bigger than inside blocks.
- **Sounds that don't play in game** (OpenGOAL, modded game): usually their bank isn't loaded, not a
  sound-engine bug. Banks are swapped per area into a fixed budget (Jak 3: six half-slots; Haven's
  `city-sound-expand-want-list` fills them in priority order; a faction's full bank takes two). Adding
  content that loads more levels at once (more factions, extra areas) silently pushes a bank out.
  Find which bank has a name by searching the `.SBK` files for it (lowercase, `_` for `-`), log the
  loaded banks when a name lookup fails (`Player::PlaySoundByName` returns 0 quietly), and reorder the
  priority list rather than adding slots (the overlord's banks mirror PS2 SPU memory). Some names the
  code plays exist in no bank at all: leftovers, harmless.

## Files

- `scripts/vagwad_music.py` - decode streamed music: `python vagwad_music.py <iso_data/jak3> <out> DESERT
  WASCITY`, or `--list`. Standard library only.
- `scripts/hfrag_to_glb.py` - the hfrag height field and its Wang sand to a glb (+ a half-resolution
  collision glb); `--sand TILE.png` uses a ready tileable picture instead.
- In jak3-ue5: `tools/glb/find_props.py` / `place_props.py` (pieces of a level mesh, replacing them),
  `tools/audio/stage_audio.py` (the sound list).

## Jak 3 city population (lesson)

- Haven's people and enemies are traffic objects: `want-count` per `traffic-type`, set from
  `*want-count-levels*` by each faction's current level (`traffic-manager-method-22`). Scale there;
  each type has 20 inactive slots, so cap at 20. Spawning is on demand, so going up to 20 a type
  gave no "traffic-manager: unable to spawn".
- When counting processes by type name, list the names first: Freedom League guards are
  `crimson-guard` (not `guard-*`), KG robots are `roboguard-city`, `spydroid`, `flying-turret`.
- Measure where the user plays, from their save: test boots don't have the story's faction state,
  so the war zone can be empty there.
- Past 20 a kind: the traffic engine's `inactive-object-array` (20 per type, stride in
  `reset-and-init-from-manager`, check in `add-reserved-process`) and the trackers' 126 active slots
  are fixed arrays; enlarging them is safe once the explicit `:offset`s after them are dropped (they
  were the natural layout). The next wall is the nav meshes' `nav-max-users` (res lump, default 64):
  `new-nav-control` returns #f when full and some callers crash. Raise it and test the busiest spot.

- Raising Jak 3 traffic counts: every citizen holds a slot of the static `*default-nav-mesh*` (128
  slots) from its init, even while inactive in the pool; the street meshes are a separate limit.
  The crash ("too many users for nav-mesh #f", then a turret/spydroid without nav) came from that
  default mesh. Fix at the source: `citizen-spawn` refuses when the default mesh is nearly full; also
  make `traffic-activate` itself refuse on a full target mesh (missions and the war zone send it
  directly, bypassing the traffic engine). `go` inside an event handler doesn't leave it: guard
  everything after `go-inactive`.
