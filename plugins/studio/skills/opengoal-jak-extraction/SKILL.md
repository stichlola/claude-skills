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

## Dev loop timings and shortcuts (measured, Jak 3, Jak Enhanced)

- **`(ml "goal_src/jak3/<file>.gc")` hot-loads one file into the running game in ~1 s** (most of it
  og_repl's Python start and sleeps; compile+load is tens of ms); top-level forms run again (globals are
  re-created). Compile errors show in goalc's stdout ("-- Compilation Error! --"). A form that generates
  code (`(begin (m ...) 7777)`) fails without a listener: send `(m ...)` alone.
- `(mi)`: cold ~30 s (1169 targets "need rebuilding" in a fresh goalc), warm no-change ~1.5 s, but one
  changed **engine** file cascades to every later file of the sequence (target2.gc → 828 targets, 24-65 s).
  `(ml)` doesn't spare that: the next `(mi)` still cascades, it is only needed for the next boot's CGO.
- goalc started with stdin at EOF (redirected file) **spins one core at 100%**: keep stdin an open pipe.
- `multi_run.ps1` skips an instance number whose goalc port is taken, even by your own goalc: the gk then
  lands on n+1 and `(lt "127.0.0.1" <port>)` must name its port.
- **`gk --no-display` works for Jak 3**: boots to desert-start in ~5.5 s (windowed 14-20 s), runs at real
  speed (300 ticks/s), ~240 MB, little CPU; no renderer, so no "[enhanced] average fps" lines.
- State asserts over the REPL: Jak 3 left idle goes from `target-stance` to `target-stance-ambient`
  after ~45 s, which is when a cold goalc's first `(mi)` finishes: a check for `'target-stance` passes
  warm (t=6 s) and fails cold (t=50 s). Accept both, or match the prefix, or check right after boot.
- Back-to-back windowed test runs on the same instance: the next launch can find the gk port still
  taken for a few seconds after the last game closed; wait for the port, don't fail at once.
- gk run from a copy of `bin` (gk.exe + DLLs, 63 MB, 0.05 s to copy) with `--proj-path` works, and the
  build can relink `out/build/Release/bin` meanwhile.
- C++: a one-line change in EnhancedPost.cpp = 8-15 s compile (2.4 s parse, the rest -O3 codegen) + 0.2 s
  lib + 0.2 s link + 1.5 s `vcvars64.bat`; a small Enhanced TU still costs ~3 s (json/imgui headers).
  `--target gk goalc` costs nothing extra when goalc's sources didn't change.
  **Fix that worked**: split the 8 k-line renderer TU by topic (Light, Menu, Passes, Scene + an
  `...Internal.h` with the shared state as `inline` in a namespace) and add a precompiled header
  (`target_precompile_headers` with json/imgui/fmt/GL): one renderer edit compiles in ~2 s (was 8.3 s),
  `dev_build.ps1` 2.8 s wall, no-op 0.5 s. Check a split is purely structural with a line-multiset diff.
- **Bind the REPL/listener sockets to 127.0.0.1, not INADDR_ANY**: on any address Windows' firewall asks
  for every new gk/goalc path (each test instance's shadow copy is a new path), the user keeps getting
  "allow access" dialogs. Old binaries keep asking until rebuilt; "Cancel" is harmless.
- Jak Enhanced's loop scripts (`scripts/enhanced/`): `dev_launch.ps1` (shadow bin, dev goalc, waits for
  the port), `dev_reload.ps1` (GOAL), `dev_build.ps1` (C++), `dev_test.ps1 <scenario.json>` (headless or
  windowed, expects log lines / REPL answers, exit code = pass/fail), shader and tuning reload on save.
  Measured: GOAL change in game 0.44 s, C++ change ~3 s + relaunch, shader 2-9 s, tuning ~1 s.
- A .bat calling `vcvars64.bat` prints "vswhere.exe is not recognized" (harmless) unless
  `%ProgramFiles(x86)%\Microsoft Visual Studio\Installer` is on PATH; write .bat files with CRLF (an
  LF-only .bat with a `rem` line gave "filename syntax is incorrect"). In Windows PowerShell 5.1,
  `git commit -F -` fed a here-string fails (pathspec error): write the message to a file.
- Scenario variants (dev_test.ps1): `wait` = game time to let pass before the variant acts, `settle`
  = after it; a single "wait" applied after the eval was misread as "before" and tested nothing.
- `JAK_ENHANCED_SHADER_RELOAD=1` reloads `enh_*` shaders on save (poll 4x a second: enh_ssao 0.2 s save to
  reloaded; the 247 KB composite 2.6 s for a comment change, but 11.5 s once `main` was wrapped in another
  function: the NVIDIA optimizer, and the frame stalls meanwhile). `=all` also reloads the game's shaders:
  their renderers look uniform locations up once (and TextureAnimator keeps the program id), so copy every
  uniform value into the new program and keep the old one if a location moved. world.json and
  tuning.json (EnhancedTune: `shaders.tune_*` feeds `uniform float tune_x = <default>;`) reload on save.
- **Call C++ from the REPL without `(mi)` and without touching kernel-defs** (which cascades every file):
  put the `define-extern` in the form, and pass commands as pseudo variables of an existing kernel
  function: `(begin (define-extern pc-enhanced-getenv (function string string int symbol))
  (pc-enhanced-getenv "JAK_ENHANCED_DO_RELOAD_SHADERS" "" 0))` round-trips in ~0.3 s.
- After gk restarts, the kept goalc must `(lt "127.0.0.1" <port>)` again, or every form fails with
  "Compilation generated code, but wasn't supposed to". Test configs on the Performance preset may have a
  pass (SSAO) off: a test on its shader shows nothing; use the composite.

## Hot-loading GOAL with answers (lesson, Jak Enhanced `scripts/enhanced/dev_reload.ps1`)

- Jak Enhanced has it ready: `dev_launch.ps1` (gk from a shadow bin + dev goalc), `dev_reload.ps1
  -Instance n` ((ml) of each changed file: OK/ERROR file:line/NEEDS, 0.2-0.6 s, was 35-90 s).
  Run as `& ([scriptblock]::Create(...))` they have no `$PSScriptRoot`: pass `-Repo <jak-enhanced>`
  unless the cwd is the repo ("-Repo: not a jak-enhanced tree"). Verified end to end: build.bat
  relinks while a game runs from a shadow bin; a first composite reload compiles ~8 s (later ~30 ms).
- **gk accepts one goalc connection per run** (`Deci2Server::accept_thread_func` returns after the first
  client): a second goalc gets "Failed to get version number". So keep one goalc alive and restart
  only gk. **Never probe the gk port with a connect** (it uses up that one accept): test it by binding.
- goalc's stdout to a pipe is **block-buffered**: GOOS `print`, prompts and some compiler output sit in
  the buffer; lines through the logger (`lg::print`: warnings, "-- Compilation Error! --") flush it. To
  delimit an answer, send after each form a marker that fails on purpose, `(seval (error "TAG"))`: its
  error block flushes everything before it; wait for the block's last line ("REPL Error: ...") too, or
  its tail lands in the next answer. Prompts (`g >`/`gc>`) come out late and out of order: read the
  listener state from text ("Got version", "already connected", "listener isn't connected").
- Don't stop goalc with `(e)` while connected: its exit path sends a reset to the game. Kill it.
- Put goalc in a job object with KILL_ON_JOB_CLOSE when a daemon owns its stdin pipe: if the daemon
  dies, a goalc with a closed stdin spins a core forever.
- `(lt)` with no game retries for a long time (each refused localhost connect costs ~2 s on Windows):
  check the port first. Same for clients: `TcpClient.ConnectAsync(...).Wait(300)`, not `Connect`.

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

## Testing post-process shaders by hot reload (lesson)

- A reload can lag several seconds: a shot may show the previous variant, and two "different" results are then the same one. Paint the variant's number in a corner of the frame and have the capture wait for that value. A second pass (AO) reloads on its own: send its mark through to the final image too (write it into the AO output, show it in the composite).
- A scene that changes over time (a fight, a passing hour, a moire drifting with the camera) makes frames incomparable. Compare inside one frame: left half unchanged, right half variant, `uv.x > 0.5` in the shader.
- `HEAD~1` as "the old shader" breaks when another agent commits meanwhile: name the commit by hash. Getting this wrong made me clear my own change of a bug it had caused.
- Check the hour really changed before reading a test: send the REPL's `'change 'hour` twice, the first after a boot can be lost.
- Normals rebuilt from depth with 1-pixel neighbours give a moire of dark rows on ground nearly level along the screen's rows (rounding of depth, a period of tens of rows). Take them from about 32 pixels apart on what's flat, and keep the renderer's own smooth normals on the terrain's grid.
- Lights at night: don't apply eye adaptation and night boosts on top of dynamic lights, adaptation measures only the dark scene. And every glow sprite as a light includes the sky's: the sun, moon and stars sit 1 m from the camera, kilometers wide.
- Remade tiling textures: detail that looks good in the flat picture can vanish in game, because one tile covers a small part of a mountain. Ask the generator for a few huge features across the whole picture, pull its pure blacks and pale edges toward the rock's median after, and match the median (not the mean) to the original. Compare with a live key that re-uploads from disk, so a new picture needs no restart. Reset the hour before each shot: game time moves on and a dusk shot looks like a broken texture.

## Diagnosing a broken light: look at each term alone

Before tuning, show every ingredient by itself in one run (hot-reloaded shader, same view, the hour set again before each capture because it keeps moving): the raw image, the normals, the relight mask, the shadow term, the material tags. Then switch each system off in turn. Rock that `broke'' at noon took three wrong guesses until the views showed it: the relight went by normals alone on rock the shadow map had in shade. Read the helper before testing it: a soft normal that stops at 40 m can't prove anything on far rock. A hypothesis that changes no pixel is wrong, so test it before telling the user.

- Impostor looks taken from another angle: compute the elevation of the lowest atlas view. A plain hemi-octahedral 8x8 grid starts at 8-11 degrees, but far objects are seen at 3-6, so flat stones show their top. Square the view height in both bake and shader (lowest about 1 degree), then rebake everything.

## Playable NPCs in Jak's place (lesson: Jak 3 Ashelin, Sig)

- Use the NPC's own art group first: its idle/walk and the clip where it holds its gun (Sig's
  `wasdoors` idle holds the Peacemaker upright like a staff); fall back to Jak's clips only for actions
  the NPC lacks (run, jump). Moving: overlay the NPC clip's arm hold (captured at init, hold-local) on
  the walk/run. Firing: tip the forearm/hand toward the fire direction procedurally (check the
  arm-along-shot dot ~1.0 in the log); muzzle = the NPC model's own blast joint.
- No long-idle fidgets: Jak's random idle variations look wrong on another body.
- Unarmed rest pose: small turns on the upper arms/forearms (arms in, elbows a bit bent); a pose the
  user makes by hand in Blender (dump the bone rotations to JSON) can be applied as turns on idle0.
- One gun per D-pad direction; reuse Jak's gun HUD (same frame, slide-in) with the character's icon
  swapped by texture name and only that direction's arrow lit; hide ammo for a gun without ammo.
- The NPC's own fire sound lives in a level bank (Ashelin's in DESERT4): load that bank as the mode
  bank (overlord AllocateBankName must give the mode slot to any bank requested as mode bank).
- Keep an unfinished character out of the menu with a gate (env override for developers) so a release
  can ship while it's in progress.
- **Retargeting onto Jak's bones: measure against his prejoint, not his root.** Jak 3's prejoint
  (node-list 2, parent of main) leaves his root by up to 3 m for a few frames in the walk/run channel
  blends (stance->walk stack, tiny walk-left/down weights) and slides back 0.6 m/frame; seen with Jak alone,
  headless and windowed. A skin placed "where Jak's main is" jumped away and back ("teleports while
  moving / after a punch"). Fix: take Jak's root with its translation replaced by the prejoint's (keep the
  root's turn: the dive tilts the prejoint for real), except pilot/ledge/pole/vehicle states.
  Jak's bones are current when a child process runs (target has sync-math), so no frame lag.
- A scaled (taller) skin: scale Jak's joints around the skin's own drawn root (control trans +
  cspace-offset), never around control trans, or cspace-offset gets multiplied by the size.
- After moving bones in a post, recompute `draw origin` as do-joint-math does (bounds xyz through
  `vector-norm-matrix*!` of `(-> draw skeleton bones origin-joint-index)`, w = bounds w): ja-post left
  it on the clip's hips, up to 5 m off the drawn body (culling, lights, shadow).
- Measure jumps in one test run with an env-gated hook: per frame, |skin main - skin root| change; run
  the old and new code paths in two phases of the same run (a global toggle) and print max per phase.
- goalc for Jak Enhanced needs `--user-auto` (jak3 maps to jak3_pal); `dev_goalc.ps1 -Instance n`
  already passes it. Headless gk (~240 MB) is enough for skeleton/state measurements when RAM is tight.

## Invisible particles and borrowed-level crashes (lesson, Jak 3)

- OpenGOAL sprite shader (`sprite3_3d.vert`): the camera w is **negative in front** for 2D and 3D sprites
  alike (as pfog0). A behind-camera cull must test `Q = pfog0 / w <= 0`, never `w <= 0`, or every
  particle in view vanishes (here: the arena training's orbs). To tell "not spawned" from "not drawn",
  count live particles by owner in the REPL: walk `*sp-particle-system-2d*` `cpuinfo-table` (valid,
  `key proc` type). Shaders load from the source tree at boot: a restart tests a shader change.
- A level borrowed in another level's slot (`master-level`) must leave the want list no later than its
  master, or `unload!` breaks ("level X is unloading but level Y depends on it"). Code that keeps it
  wanted must check the master is still in `load-state want` (not just loaded), and in `want-levels`
  look the master up before the loop clears matched names from the new list. Test a trip with
  `(process-spawn scene-player :init scene-player-init "<scene>" #t "<continue>")` (air train:
  `desert-air-train-in`, from `desert-warp` to `ctyport-warp`); start a mission with
  `(dm-play-task-with-continue (game-task <task>) (the-as string #f))`. PowerShell strips `"` from native
  arguments: write `\"` inside the form.

- Impostors vs tilted copies: compare near and far in ONE run (flip the detail distance every few seconds), not across runs. A tilted copy seen from below its own horizon has no view in a hemisphere atlas and a flat quad shows what the ground hides: keep its LOD instead of baking more views (16x16 with views below the horizon looked worse: fatter rocks). Scale mip alpha per atlas cell, not per atlas.


## Clock jumps and testing beside the user's game (lesson, Jak 3)

- Never run `bg-clock frame-counter` below 0: just after boot it is only a few hours in, and a
  "short way round" hour change that goes back past 0 makes the time of day negative; code that
  steers toward an hour then chases it backward forever (here: a "this evening" log line every frame,
  then 0xC0000005 in GOAL memory). Go forward round the day when going back would cross 0. A bug
  "only right after the game starts" often means a counter that is still small.
- Reproduce with the user's own settings: copy their `enhanced-settings.json` into a test config dir
  (theirs had another player model, weather, population that the test config lacked).
- While the user's gk runs it holds the REPL ports (gk's Deci2 port is hard-coded per game): a second
  gk boots without them and `(lt)` connects goalc to the USER's game. Drive tests with a temporary
  env-gated hook in GOAL instead (`pc-enhanced-getenv`, log values every frame), start your gk
  minimized so it doesn't take their keystrokes, and remove the hook before committing.
- GOAL `format` takes at most 8 arguments in all (destination and string included).

## Running several game instances in parallel (lesson, Jak Enhanced)

- Stock gk/goalc ports are fixed per game (Deci2 8112-8114, goalc nREPL 8181, debug 8128-8130; and
  `runtime.cpp` ignores `--port`, which is a CLI *flag* anyway). Jak Enhanced: `JAK_ENHANCED_INSTANCE=<n>`
  moves all of them by **10*n** (not n: +1 would land on the next game's default port), logs go to
  `<game>_i<n>.*.log`; start goalc with the same variable, `og_repl.py --instance n`. Unset = stock.
- One config dir per instance (`--config-path <dir>`, which holds `OpenGOAL\<game>\settings`), copied
  from a test config: never the user's `%APPDATA%\OpenGOAL`. Windowed = `display_mode 0` in
  `display-settings.json`; a `window_xpos/ypos` at or left of the screen edge (0) is reset to 50.
  Set `window-size` in `pc-settings.gc` but leave `game-size`: it is the fullscreen resolution and
  640x360 there is "invalid" (falls back to the desktop's); windowed renders at the window size.
  Quality: `JAK_ENHANCED_PRESET=3` (Performance).
- A worktree's own gk can't find the data (it looks for a parent named `jak-project`): pass
  `--proj-path <main tree>`; logs then land in the main tree's `log\`.
- Launch with `ProcessStartInfo` (`UseShellExecute=false`, `CreateNoWindow=true`, per-instance
  `EnvironmentVariables`), place the window with `SetWindowPos(...NOACTIVATE)` and hand focus back with
  `SetForegroundWindow(previous)`; `GetClientRect` from DPI-unaware PowerShell reports 640x360 as 512x288
  at 125%. Crashes: exit code plus Application event 1000 (see below).
- **Collecting crashes** (`scripts/enhanced/crash_collect.ps1`): event 1000 `Properties` are
  0 app, 3 module, 6 code, 7 offset, 8 PID (a UInt32, decimal: only the Message text shows it in hex),
  9 process start (FILETIME), 10 exe path. Module `unknown` = GOAL/JIT code, the offset is then an
  absolute address. Event 1001 (WER) carries the ReportArchive folder; match it by time + offset.
  Minidumps: `%LOCALAPPDATA%\CrashDumps\gk.exe.<decimal pid>.dmp`. The gk log is named after the
  process start (`jak3_i3.2026-11-07T11-02-13.log` = start 11:02:13): match on it, tie-break on the last
  write time (instances often start in the same second). gk keeps only ~10 logs per name, so a
  crash from a few hours of tests ago has lost its log: collect right away or watch. `jak-project` is
  often a junction to the real tree: follow it or each log is listed twice. Open live logs with
  `FileShare ReadWrite`. In a script run via `[scriptblock]::Create`, `$PSScriptRoot` is empty and
  `exit` closes the caller's console: use `return`; `$Pid` is PowerShell's read-only `$PID`.
- Capacity (RTX 5070 Laptop, Ryzen AI 9 365, 32 GB, jak3 desert-start, Performance, 640x360): each gk
  ~2.8 GB peak working set; 2-4 instances all held ~50-58 fps, 4 left 0.5 GB available RAM, so 3 is
  the default max. RAM, not GPU, is the limit. Script: `scripts/enhanced/multi_run.ps1`.

## A themed in-game menu and capturing it (lesson, Jak Enhanced)

- Restyle one ImGui window without touching the others: push the style vars and colors in an RAII
  object at the top of its draw function (popped on every way out), and draw custom widgets (switches,
  segmented rows, filled sliders) only while a "styled" flag is set, falling back to ImGui's own outside.
- A theme per game: keep the palette in a struct table indexed by the game, copied into the globals the
  widgets read when the window opens; an env override (`JAK_ENHANCED_MENU_THEME=1..3`) lets one game
  show every theme for screenshots. `JAK_ENHANCED_MENU=1` opens the menu at boot.
- Long switch grids read badly: group them in collapsible tree nodes by topic (image, light and
  shadows, night, sky and weather, surfaces, world, effects, water, sound), keep only the master switch,
  auto quality and the presets always visible, and move non-graphics buttons (nap, feedback) out.
- Capturing the game window for review: `SetProcessDPIAware()` first (else a 125% screen crops it),
  then `PrintWindow(hwnd, dc, 2)` on the biggest visible window of the gk PID. A minimized window
  captures as 199x34: start the test window normal (small, windowed config) and close it after.
- While a gk is running the dev build can't relink (its DLLs are locked); to check a C++ edit for
  errors meanwhile, build only the object: `ninja game/CMakeFiles/runtime.dir/<path>.cpp.obj`.
- Dev gk started from the real repo path fails with "Failed to initialize project path": start it from
  the `jak-project` junction (or pass `--proj-path`).

## A release gate and test hooks from GOAL (lesson, Jak Enhanced `scripts/enhanced/release_gate.ps1`)

- One windowed test boot per scenario row, judged from the outside: process alive, no Application
  event 1000 for its PID, enough `[enhanced] average N fps ... in <level>` lines (level order for level
  changes; count the boot's own line too, a fast change happens before the run's first line),
  screenshots not black (PrintWindow + mean luma), and the row's log lines in order. Give every check a
  log line of its own (env-free, one per event): "hour request/reached", "nap start/end", "weather mode
  <n>", "scene <name> start/end", "auto-save <mode> done|error". A full Jak 3 pass: ~25 rows, ~40 min.
- **A GOAL global's value is 32 bits**: a `handle` (pid in the high half) stored in a `define`d global
  loses its pid, and `handle->process` then always says #f. Keep the process pointer and its pid as two
  globals, or find the process by name (`process-by-name "scene-player" *active-pool*`).
- **`format`'s `~A` prints strings with quotes, `~S` without** (`[x] "ashelin"`): write the checks'
  regexes with optional quotes, or log names with `~S`.
- A GOAL `lambda` can't see the enclosing `let`'s variables: pass data through globals.
- A request queued at boot (`JAK_ENHANCED_MENU=2:<cp>`) is taken in the first frames, before the first
  fps line: to test a level change *from* the start point, queue it on a timeline
  (`JAK_ENHANCED_MENU_SCRIPT=<s>:<kind>:<value>,...`).
- Gated game content needs its task: Jak 3's desert air train only runs to Haven after
  `city-destroy-grid-resolution` (its on-notice); a test closes it with `(task-close! "...")` first.
- A worktree that builds its own game: configure CMake in `out\build\Release` (Ninja, clang, ~2.5 min
  for gk+goalc with -j 10), copy `goal_src\user\<user>\repl-config.json` + `user.txt` (else `(mi)` looks
  in `decompiler_out\jak3\` and misses `game_text.txt`), junction `iso_data\jak3_pal` from the main tree,
  and hardlink the main tree's `out\jak3\fr3` files the worktree lacks (a half copy loads the desert but
  dies at the first missing level). `goalc --proj-path <wt> --user-auto --cmd "(mi)"` builds it.
