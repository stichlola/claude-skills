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

## Adding player states and talking to GOAL from C++ (lesson)

- A request channel C++ -> GOAL: a small `(kind, string)` mailbox the C++ side fills and a GOAL
  function polls every frame (`pc-enhanced-poll-request`), dispatching by kind.
- That poller runs inside the target's post (`flag-setup`): it must **not** `go` to a new state.
  Set a global flag and let `target-stance`'s `:trans` start the state (on the ground, no gun), and
  drop the request after ~2 s if Jak never stood still.
- Load order matters for new states: logic-target.o -> target.o -> target2.o. Declare
  `(define-extern target-x (state target))` in target.gc and define the state in target2.gc.
- Clock: `(send-event (ppointer->process *time-of-day*) 'change 'ratio r)`; ratio 1.0 is normal
  (one game hour per real minute, a day in 24 min), so N hours in 5 s is ratio `12*N`. Read the
  hour with `(the-as time-of-day-proc (ppointer->process *time-of-day*))` - the bare pointer is
  `process` and has no `time-of-day` field. Restore the ratio in `:exit` (a hit can end the state).
- Lying down: Jak II and 3 have no sleep animation, but `target-load-wait` makes Jak trip
  (`jakb-trip-ja`), holds him flat by seeking to aframe 19 at 0.05, then gets up with
  `jakb-painful-land-ja` from aframe 40 + `jakb-painful-land-end-ja`. `painful-land` from 40 is
  the *getting up*, not the fall. Verify a short animation with a capture every ~1.2 s, not one shot.
- Testing a cutscene: spawn `scene-player` with the scene name from an env var once the level is
  up (`JAK_ENHANCED_SCENE`). The Jak 2 hour override must wait for `*target*`.
- A release's launcher runs `gk.exe --game jakN -- -boot -fakeiso` from its folder; testing a
  fresh install with `--proj-path` makes gk quit at once with an empty log.

## New animations for Jak (build-actor, lesson)

- Retarget a Mixamo clip in Blender headless (`--factory-startup`, or the user's addons break it):
  Mixamo X Bot and the ripped `jakb-lod0.glb` / `eichar-lod0.glb` are both T-pose facing -Y; give
  each Jak joint the world delta rotation of its Mixamo joint from the T-pose, unmapped joints follow
  their parent. Bind pose `main` is scaled 1.4; animations run at 1.0 (`main` 1.028 m up).
- `build-actor "<name>" :master-art-group "jakb-ag"` (Jak 1: `"eichar-ag"`) turns a glb into
  `<name>-ag.go`. The glb skeleton starts at `prejoint` (build-actor adds `align` itself); every
  joint needs T, R and S on every frame (missing channels become identity, not the rest pose); the
  mesh needs indices, a material and u8 JOINTS_0, or build-actor crashes (0xC0000005 / 0xC0000409).
  A one-triangle mesh is enough for an animation-only group.
- Put the .go in GAME.CGO (`game.gd`); Jak II/3 also need `(hash-table-set! *file-entry-map*
  "<name>-ag.go" #f)` before `cgo-file "game.gd"`, or "multiple ways to make output".
- Only Jak 3 links GAME.CGO sub-groups into `jakb-ag`. Jak 1 and II link only art groups whose
  first entry is an animation: keep the group in a global from `art-group` `relocate` (joint.gc)
  and `get-art-by-name` from there.
- The decompiler's `rip_levels` writes glbs to `decompiler_out/<game>/levels/common` whatever the
  output folder, and a GAME.CGO-only rip rewrites `out/<game>/fr3/GAME.fr3` without the levels'
  animated textures (Jak II crashes: "no texture named security-env-dest"). Rerun the full
  decompiler afterwards.
- Jak 1 screen UI: sprites and text use 512 x 224 (y halved from 448), `draw-string-xy` with
  `middle` centers on x, no font scale, and the large font has only capitals and the pad glyphs
  (lowercase comes out as kanji).

## HD HUD, menu and minimap art (lesson)

- Texture replacements baked into the levels (`custom_assets/<game>/texture_replacements`) break
  anything drawn by the direct renderer in texel units (HUD, minimap, menus): the shader divides by
  `textureSize`, so a 4x texture shows a quarter. Load those at runtime instead (`add_texture` in
  `LoaderStages.cpp`) and register a texel scale per GL texture that the direct renderer passes to
  its shaders (`tex_px_scale`). Forget the scale at every `glDeleteTextures`.
- Jak II/3 minimap: district maps are 4-bit `map-*` textures in `*-minimap` pages, icons a 128x128
  atlas of 20 px cells (`mini-map-icons`, PS2 alpha 128 = opaque). Jak 3's pause-menu big map is a
  different image (`WOMAP.STR`, uploaded 256x416 at a time while scrolling), not these textures.
- Minimap size: everything on screen is relative to hud-map's ring position; scale the map sprite
  (112 px), the icon matrix (rvec/fvec), icon size (20) and ring together around it.
- Ship only new drawings. For an atlas partly redrawn, leave the cells not redrawn as see-through
  magenta (RGB 255,0,255, alpha 0) and fill them at load from the game's own texture, enlarged.
  Upscales of game art are made on the player's machine from their disc (installer asks, with time).
- A Windows setup .exe (Inno Setup 6, per-user, `PrivilegesRequired=lowest`) over the release folder:
  custom pages (ISO pickers, HD option per game) only write small files (`ISO\iso-paths.txt`,
  `data\hd-textures-jakN.txt`) that the .bat launcher reads, so the zip and the setup share one flow.
  Gotchas: an .iss with non-ASCII text needs a UTF-8 BOM; `/VERYSILENT` skips the pages but still runs
  `NextButtonClick` (guard validation with `WizardSilent`, or the silent test exits 1); test with
  `/VERYSILENT /CURRENTUSER /DIR=<tmp> /LOG=<file>` then `unins000.exe /VERYSILENT`.
- Don't ship scripts that need `powershell -ExecutionPolicy Bypass` to end users: do image work in
  Python (Pillow/NumPy) and call Real-ESRGAN's exe directly.

## Game text is not rebuilt when the encoder changes (lesson)

- The `text` tool reruns only when the text sources change: a change in the C++ text encoder (e.g. button
  glyph sequences in `font_utils.cpp`) never reaches `out/jakN/iso/*COMMON.TXT`. Delete those files and
  `(make-group "text")`, and make the launcher delete them on a version change before recompiling.
  Hand-drawn test strings in GOAL won't show the stale text: test a real game message.
- OpenGOAL's `AI_POLICY.md`: no AI-co-authored commits, no AI code in `goal_src/` from new contributors,
  no AI media. An AI-built fork belongs in its own repo / a launcher mod source, not upstream PRs.

## Fast test boots through the REPL (lesson)

A test run went from ~37 s to ~20 s (game boot only) with the screenshot taken the moment Jak stands
at the saved spot:

- **Keep goalc running between game restarts.** `(mi)` takes ~35 s every time goalc starts (it needs
  the types to compile forms that touch `*target*`); kill only gk, and `(lt)` reconnects the same goalc
  to the new game. Start goalc and its `(mi)` in parallel with the game's boot the first time.
- **Don't wait on a periodic log line** (an fps average every 5 s): wait for the first one that means
  "frames are coming", then ask the game itself.
- **The nREPL socket returns nothing**: read answers from goalc's stdout log. Send
  `(if <condition> 7777 0)` and count `7777` in the log before/after.
- **Jak is there before he is in place**: `*target*` exists at once, then the continue point and the
  camera intro put him back. Wait for `(= (-> *target* next-state name) 'target-stance)`, place him,
  check `(vector-vector-distance (-> *target* control trans) <spot>)` a moment later, repeat; and send
  the placement once more ~1.5 s after it holds.
- **One form per call**: each og_repl call reconnects (~0.5 s); wrap setup forms in one `(begin ... 0)`.
- Window capture (PrintWindow/BitBlt of the client rect) takes 0.2 s: capture right after "ready", no
  sleeps.

## Gameplay options gated from C++ (lesson)

- A menu switch reaches GOAL as a kernel function: an atomic in C++, `make_func_symbol_func("pc-x?", ...)`
  in kmachine, `(define-extern pc-x? (function symbol))` in kernel-defs. Read it where each value is set
  (`(if (pc-x?) new old)`), so off means byte-for-byte the original game; off by default.
- Where to hook: enemy damage taken is one method (`damage-enemy-from-attack!` in enemy.gc: multiply a
  blow, reward a kill when hit points cross 0); the player's knockdown is `target-attacked`
  (target-handler.gc): turning an ordinary hit's mode into `'damage` costs health without the stagger,
  but keep `attack-mode-is-invinc` modes (lava, falls, crush) as they are. Ammo per shot: the
  `ammo-required` case in target-gun.gc (pickup-type numbers from game-info-h).
- Test through the REPL: give the power (`features`, `eco-pill-dark`), `'change-mode`, send an
  `'attack` with `static-attack-info`, then read `fact health` and `next-state`. (`(lt)` fails while
  another goalc still holds the listener: restart both.)
- `.gc` files are CRLF: patch scripts convert their search text to CRLF or the match fails silently.

## Crossing from GOAL to C++, and testing an editor (lesson)

- GOAL's `#f` is not a null pointer in C++: it's the address of the false symbol. An optional pointer
  argument must be checked against `bool_to_symbol(false)` too, or C++ reads garbage from it. The symptom
  looks random (here: collision lost terrain and placed objects now and then).
- An incremental `(mi)` doesn't always see a global defined in another file: add `define-extern` at the
  top of the file using it. After every GOAL change, search goalc's log for "Compilation failed": the game
  still starts, with the old code.
- Processes are paused while a full-screen tool is open. Anything that must happen then goes in the display
  loop (`display-loop-main`), not in a process's update. Test the path a user takes (tool open), not only
  a script's shortcut.
- A light or color borrowed from "the first vertex of the first tree drawn" depends on the camera and on
  the place: painted content came out black in one area only. Pick a percentile over the tree's vertices.
- Test scripts: let the running game reload a changed script file when the last one has finished, so each
  try doesn't need a boot. Drive the real UI, and have a real run read the files back before a release
  (undo, save, export, import).

- When a game has two ways of drawing the same models (replacing the game's props, and objects placed by an editor), check level-of-detail on both: having the files doesn't mean a path loads them. To compare a change, switch it with a temporary flag file inside one run and log the triangles drawn: with vsync on, fps stays at the cap and shows nothing (here 3.57 M against 0.71 M triangles, both about 58 fps).

## Replacing a static actor's model (tested: Jak 3 market props)

- `custom_assets/jak3/merc_replacements/<model>-lod0.glb` (and `.json`) works for a one-bone prop with no skin: fit the mesh to the ripped glb's box, keep +y up, nearest-vertex weights do the rest.
- No need for a full extraction: pass `"inputs_file"` in `--config-override`, pointing at a copy of `inputs.jsonc` whose `levels_to_extract` lists only the DGOs that hold the model (about 2 minutes). `GAME.fr3` is rewritten too: back up what changes first.
- A glb without `COLOR_0` loads as white (0xff), twice the game's neutral 0x80, despite what the doc says: it looks washed out. Halve the picture's values, or export the colors.
- Each model embeds its own copy of a shared Tripo atlas, uncompressed in the fr3: at 2048 a level went from 42 to 181 MB, at 1024 to 52 MB.
- Finding which post effect draws an artifact: `JAK_ENHANCED_SHADER_RELOAD=1` reloads `enh_*` shaders while the game runs. A script that swaps one line of the shader per variant and takes a shot of each compares them all in one run, with the same camera. Restore the files in a `finally`.
- PowerShell: a negative number passed to a function arrives as a string, and `$z * 4096` then repeats the string. Cast with `[int]`.
- Prompts for a remake: "same shapes, exactly the same colors and scale" gets a faithful copy that barely shows in game. Ask for more detail and allow new forms; match the colors afterwards.
