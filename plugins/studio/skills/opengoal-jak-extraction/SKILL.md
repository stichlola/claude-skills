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
- Test runs must be **silent** (user rule). Jak Enhanced's gk writes zeros to the audio output when
  `JAK_ENHANCED_MUTE=1` or `JAK_ENHANCED_INSTANCE>=1` (`game/sound/989snd/player.cpp`). The synth still
  ticks, so game timing is unchanged. The user's own game (no instance set) keeps its sound.
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
- Pointing a test at water (Jak Enhanced): a late teleport (`JAK_ENHANCED_MENU_SCRIPT` `22:3:x/y/z/yaw`) moves Jak and turns him, but the camera keeps its heading, so pick the spot along the start camera's own view. Haven port: `ctyport-start` + `22:3:193/17.5/1725/180` puts Jak swimming in the harbour, facing the far quay. Check the water debug mask in the first shot: a "water in view" is not proof the composite treats it as water.
- Spargus sea (Jak 3): `wascitya-seem` and `wascitya-start` see no sea, even with `JAK_ENHANCED_PLAYER_TEST=orbit` turning the camera. The ocean-mid mask (`wascity-ocean.gc`, corner -256/-2762 m, 96 m tiles) has sea west of x ~2134 m and north of z ~ -400 m around Spargus, but a menu-script teleport there (`3:2110/9.5/-60/180`) ends back at the continue point (deep sea = death). Reach it from the air (Hellcat test) instead. Before tagging textures for a night effect, boot with `JAK_ENHANCED_MATERIAL_NAMES=1` (each texture's name and class per level) and look at the tag debug view (`tune_night_win 10`: magenta = any glossy pixel, metal included; cyan = window panes): at the Haven port 22h the far quay's bright strips were metal, not glass, so retagging `fac-lo-glass` changed nothing there.
- Water bands: before calling a pale strip under a far quay a seam, look at the hit view (Jak Enhanced
  `tune_water_dbg 6`). No hits from ~25-50 m in both tracers (Hi-Z and the old march, `tune_hiz_dbg 1`
  splits them) means the rays go over the quay into the sky: a correct sky reflection, not a bug. A
  real seam lines up with a change of depth source (`tune_water_dbg 7`, e.g. where the game's near
  ocean mesh starts). Find it with a per-row RGB profile of a column strip across all the debug views
  (mean of 80 px per row, every 2 rows), not by eye. Spargus sea 18h: a dark 4-row line sits there.
- `JAK_ENHANCED_HELLCAT_TEST=2` (desert to Spargus in the Hellcat) is over before a windowed boot's first
  "average fps" line (~35 s): every capture timed from there shows Jak already standing at wascitya-start.
  It is no way to see the Spargus sea.
- Darkening the ground at the foot of grass (Jak 3 forest, `forest-pillar-start` 18h): the "tufts" there are
  one big shrub tussock (shrub.frag tag 0.97 over all of it, a tag view confirms). Its blades stand 0.5-1 m+
  in front of the ground they hide. A depth probe from the lawn (one tap 25 cm up and a ring of 5 at 40 cm,
  gap < 0.5-1.1 m, shrub tag) found no hit in its debug view. A probe printing the gap itself
  (`(q.z - view_z(d)) / 1 m + 0.5`) is the next step. Show the probe's raw value before you tune thresholds.
  Pin the hour for the whole run: forest 18h became night within 3 min, and the lawn mask (green over red)
  drops out at night.
  Follow-up (Jak Enhanced `tune_lawn_foot`, off): a world-space probe (shrub-tagged pixel beside, < 0.7 m,
  and above the ground point) instead of a depth gap lands on the small tufts' outlines (lit grass-field
  blades that carry the floor's tag), not on the ground round the big tussock; foot/other luma unchanged.
  What worked (M3, on): the loader already knows where every plant stands, so keep each level's feet
  (centre, floor height, radius, height; the game's shrubs up to 3 m / 5 m round too: the forest
  "tussock" is ~110 `fora-shrub-grass-*` shrubs 1.9 m tall that fail the 1.6 m "grounded" test), splat
  them on a worker into a world-space RG32F map round the camera (shade, shade x floor height, 0.5 m
  cells, redone every 8 m), and shade lawn pixels near a foot at its floor height. Within-frame split:
  tuft-foot pixels -17%, no post cost. Debug it with views that paint the map over *every* pixel and
  the map itself in a screen corner with the camera marked: they showed the map right and the lawn
  beside the tussock simply too far from any foot (seen from above, the ground past a 2 m tussock's
  far rim is ~4 m behind its blades, where real AO wouldn't reach either). Also: `world_dir(p)` in the
  composite *is* the world frame (up_view etc. are world axes in view space), no need to "fix" it.
  Measure such a mask as a within-frame ratio (masked vs unmasked pixels of the same half, split on
  `uv.x > 0.5`): the whole forest's luma swung +-8 between frames 4 s apart. A menu-script hour pin of
  40 steps x 15 s ends after 10 min: a long A/B session silently slid into night; reboot or add steps.
- PowerShell: `R` is an alias of Invoke-History. A helper function named `R` breaks with
  "positional parameter" errors.
- PowerShell: a negative number passed to a function arrives as a string, and `$z * 4096` then repeats the string. Cast with `[int]`.
- Prompts for a remake: "same shapes, exactly the same colors and scale" gets a faithful copy that barely shows in game. Ask for more detail and allow new forms; match the colors afterwards.

## Testing post-process shaders by hot reload (lesson)

- A reload can lag several seconds: a shot may show the previous variant, and two "different" results are then the same one. Paint the variant's number in a corner of the frame and have the capture wait for that value. A second pass (AO) reloads on its own: send its mark through to the final image too (write it into the AO output, show it in the composite).
- A scene that changes over time (a fight, a passing hour, a moire drifting with the camera) makes frames incomparable. Compare inside one frame: left half unchanged, right half variant, `uv.x > 0.5` in the shader.
- `HEAD~1` as "the old shader" breaks when another agent commits meanwhile: name the commit by hash. Getting this wrong made me clear my own change of a bug it had caused.
- Check the hour really changed before reading a test: send the REPL's `'change 'hour` twice, the first after a boot can be lost.
- **Pin the hour for a whole sweep**: game time runs on (the arena at 20h lost its sun shadow two minutes in, and a
  "fix" looked like it worked). Boot with `JAK_ENHANCED_MENU_SCRIPT` repeating the same hour every 15 s
  (`25:1:20,40:1:20,...`, 40 steps = 10 min): every tuning variant then sees the same light.
- The composite's reload after a shader *edit* lags 6-12 s+ (tuning-only changes ~1 s): a 3 s wait shot the old
  shader and made two variants swap results. After an edit wait >= 12 s, or mark the variant on screen.
- The post's `sky_sun` is not where the game draws its sun sprite: Haven's port at noon has the sprite low in view
  while `sky_sun` is ~55 deg up, off screen. An analytic sun disc at `sky_sun` can't replace that sprite (tested,
  reverted): take the glow sprite's own screen position instead.
- Characters darkened "in the sun's shade" inside a pool of the game's own light (Jak 3 arena shaft at dusk)
  go silhouette: the map only knows the sun. Gate it by the bloom on the floor *beside and below* the
  character (its own pixel's bloom is low, it's the dark thing in the pool), and only with a low sun.
- Night water "columns" with hard sides in a harbor: `tune_water_dbg 2` (no far beacons) removed them; the cap
  on the beacons' summed reflection was the fix, not SSR or the night sky keep.
- Normals rebuilt from depth with 1-pixel neighbours give a moire of dark rows on ground nearly level along the screen's rows (rounding of depth, a period of tens of rows). Taps 32 pixels apart on what's flat helped but still left straight dark lines at the same screen rows in every level (Jak 3 SSAO, y ~198/225/314 of 360). What fixed it: the G-buffer's normal on any up-facing ground (weight `smoothstep(0.7, 0.85, abs(world_n.y))`), the depth's elsewhere (crates' smoothed edges lean out of "up"). AO-view row metric -27 -> -1.7.
- Bisecting a pass by writing constants: if an artifact survives "output a constant here", the artifact's pixels took another branch. Encode the branch conditions as grey levels (0.25/0.5/1.0) instead: it shows which test those pixels fail.
- Check the effects layer is live before an A/B on anything built on it (Jak Enhanced: `tune_fx_debug 4` paints
  `fx_day` red). In a run where the game's `sprite3_3d.frag` had been hot reloaded (`SHADER_RELOAD=all`) and the
  composite twice, `fx_day` read 0 in daylight: a composite fix on `fx_rest` did nothing there, while the camera
  drift still made it look like +6%. A fresh boot had `fx_day` 1 and the same fix gave +17%. Reboot after `=all`.
- Debug switches on one shared tune value (`tune_dbgx` 1..5 = views) collide with a test switch reusing the same value: a ">4.5 = albedo view" silently ate a "6 = variant" test. One uniform per test.
- Lights at night: don't apply eye adaptation and night boosts on top of dynamic lights, adaptation measures only the dark scene. And every glow sprite as a light includes the sky's: the sun, moon and stars sit 1 m from the camera, kilometers wide.
- Two saves of a big shader a second apart: the first reload compiled (with half the edit: "undefined
  variable") and the second save was never picked up. After a failed reload, touch the file again; the
  composite took up to 20 s to reload once it was big.
- A post cost that jumps 2 -> 7 ms at one spot can be another test instance on the same GPU: alternate
  variants in 16 s windows and trust only windows where "off" is back at its old value.
- Jak 3 desert ponds are not all above the sea: desert-ashelin's oasis (x 620, z 2520 m) is the game's
  sea plane at 9 m showing through a hollow, so a "not at 9 m = pond" rule gave it the sea's look.
  A disc around it (no sea within kilometers) fixed it; check a rule with a debug view that paints it.
- Fading a level in instead of popping (Jak Enhanced `bg.fade_in`): hook the per-level setup every
  background draw goes through (`first_tfrag_draw_setup`, the level's name already set), restart when
  that level wasn't drawn for > 2 frames, dither-discard in tfrag/tie/shrub. **Count frames, not the
  clock**: a loading hitch of 0.4 s between two frames restarted a clock-based fade. Every displayed
  level sends its trees each frame whatever the camera sees, so turning round never restarts it (log a
  line per fade start and watch it while idle).
  Props and characters (merc) spawned with the level popped in whole over the dithering ground: Merc2
  reads the same per-level fade read-only by `lev->level->level_name` (the level's background buckets
  come before its merc in the frame, so a restart is already counted; no background drawn = whole, so
  Jak's common models never fade) and merc2/emerc discard on the same Bayer dither. Bayer 4x4 without
  an array: `q = x ^ y; m = ((q&1)<<3) | ((y&1)<<2) | (q&2) | ((y&2)>>1)`. Test it with a long fade
  (bg.fade_in 10) and the switch flipped mid-fade in one boot: the cactus solid over dithered ground
  with it off, dithered with the ground with it on.
- Haven port 22h: ctywide lists `citywide-window-litwindow` and `ctyslumc-window-panes-LOW` as windows
  (`JAK_ENHANCED_MATERIAL_NAMES=1` logs each texture's tag), yet painting tags 11/12 in tfrag3 and
  etie_base gave 0 pixels across the harbour: the far city has no window textures to light.
  Night windows there have to be made up (a procedural grid on its wall surfaces), not tagged.
- Before building a material tag from texture names, check that the textures are really drawn by the renderer you tag, at the spot you test. Paint that material magenta in the renderer's own shader (tfrag3/etie_base: `if (enh_material == N) color.rgb = vec3(1,0,1);`), boot once, and count the pixels. Jak 3 Haven port at 22h: the level listed 10 lamp textures (`city-*light`, `hiphog-exterior-*-on`), but there were 0 pixels at `ctyport-start` and at `ctyport-hiphog`. The glowing lamps seen there come from another path. A level's texture list says nothing about what is on screen. A post tag view that stays empty can't tell "tag broken" from "never drawn", but this test can.
- Remade tiling textures: detail that looks good in the flat picture can vanish in game, because one tile covers a small part of a mountain. Ask the generator for a few huge features across the whole picture, pull its pure blacks and pale edges toward the rock's median after, and match the median (not the mean) to the original. Compare with a live key that re-uploads from disk, so a new picture needs no restart. Reset the hour before each shot: game time moves on and a dusk shot looks like a broken texture.

## Light effects that vanish by day (lesson, Jak 3 Enhanced)

Additive sprites (shots, thrusters, fire, flares) get crushed by daytime exposure and tonemapping. They are lost against bright sand. Brightening the whole scene is not the fix.
- Copy the frame just before the first sprite bucket (`TEX_SPRITE`) and just after the last (`GENERIC_SPRITE_3`), both with mips. after − before = what the effects added. Subtract it before the grade, then re-add it after eye adaptation with a gain and a soft knee. Weight it by `1 − night` so night is unchanged. Do the same in the bloom bright pass. Measured: thruster contrast doubled at noon (Weber 0.14 → 0.28), with no cost in fps.
- Boost only compact sources. Compare the local mean of the difference (a mip around screen_h/6) with the pixel's own value, and check a mip further out too. A wash of light over a whole room (the arena shaft) fails these tests and stays in the grade. Without this test, Jak was blown out and the boost drew rings.
- A channel the sum clipped kept less than it received. Rebuild it as max(fx, max channel), or flares turn green or pink.
- A replacement sky wipes whatever the game drew over its sky: smoke, flares, glass. Keep the game pixel where it has local contrast (a 9-tap luma min/max), and re-add the non-compact sprite deltas after the clouds.
  Trap (verified): that contrast test also fires on every sky pixel next to a silhouette and on the game's own painted cloud wisps: grey halos around mountains and dirty vanilla streaks over the new sky. Fix that worked: copy the frame right after the sky bucket (Jak 3: after `OCEAN_MID_FAR`); keep only where the scene before the sprites differs from that copy *and* the difference is sharp against its sky neighbours 3 px away (skip neighbours with depth). Honeycomb back, desert skyline identical with keep on/off.
- Verify looks at `JAK_ENHANCED_PRESET=2` (the tour's): the testcfg default 3 (Performance) drops the area grade and most sun shadow, the desert noon looks near vanilla and shadows on/off are identical, so a "fixed" shadow bug can't even show there.
- Before claiming "the scene is not brighter", A/B the feature's kill switch **inside one run** (a tuning.json key, e.g. `"fx": {"off": 1}`, not an env var read at boot), and prove the switch acts (a debug view goes black). Between runs the desert noon varied 103 → 118 luma with the same code: the auto-quality stepped to level 1 (mist volume off) in the boot's first seconds (52-55 fps, GPU 17.7 ms) in some runs and never stepped back, and the game's own desert dust varies per boot. Check `auto quality N` in each run's log before comparing runs. Fix: no auto step up for 10 s after load frames.
- A mid-frame copy (`glBlitFramebuffer` + `glGenerateMipmap`) between bucket renderers must restore what it found: active texture unit, that unit's texture, read and draw framebuffers. The game's direct renderers keep textures bound on units 20+ and don't rebind while their state is unchanged.

## Diagnosing a broken light: look at each term alone

Before tuning, show every ingredient by itself in one run (hot-reloaded shader, same view, the hour set again before each capture because it keeps moving): the raw image, the normals, the relight mask, the shadow term, the material tags. Then switch each system off in turn. Rock that `broke'' at noon took three wrong guesses until the views showed it: the relight went by normals alone on rock the shadow map had in shade. Read the helper before testing it: a soft normal that stops at 40 m can't prove anything on far rock. A hypothesis that changes no pixel is wrong, so test it before telling the user.

- A shadow that "shouldn't be there": before blaming the map, show the gap between receiver and caster in meters along the light (debug view). In the Jak 3 desert basin it was ~125 m: a real cliff under a key light kept at 18 deg all day. The fix was the light (raise it around noon), not the shadow code. What's left after that is often a slope facing away from the sun, not a caster. Then find the caster: `JAK_ENHANCED_SHADOW_SKIP=none` logs every draw's box; filter the boxes over the receiver's x/z that reach above it (desert-start: Spargus' gate walls, 40-60 m high, 20-40 m behind Jak). Raising the cap to 50 deg was not enough there; 65 deg lit the basin (sweep `"light": {"max_elev": x}` in one run).
- Draws with no depth write, or with alpha test NEVER, must not cast shadows (glass, glows, decals). Alpha-tested ones cast with their texture and alpha ref, or leaves cast solid squares.
- Shadow swimming as the sun moves: quantize the light direction (redraw only past ~0.15 deg). Scale the near bias with the map span instead of a fixed constant.
- A worktree build must be launched with `--proj-path <worktree>`, or gk loads the main tree's shaders and hot-reload edits seem to do nothing.
- Impostor looks taken from another angle: compute the elevation of the lowest atlas view. A plain hemi-octahedral 8x8 grid starts at 8-11 degrees, but far objects are seen at 3-6, so flat stones show their top. Square the view height in both bake and shader (lowest about 1 degree), then rebake everything.

## Playable NPCs in Jak's place (lesson: Jak 3 Ashelin, Sig)

- Use the NPC's own art group first: its idle/walk and the clip where it holds its gun (Sig's
  `wasdoors` idle holds the Peacemaker upright like a staff); fall back to Jak's clips only for actions
  the NPC lacks (run, jump). Moving: overlay the NPC clip's arm hold (captured at init, hold-local) on
  the walk/run. Firing: tip the forearm/hand toward the fire direction procedurally (check the
  arm-along-shot dot ~1.0 in the log); muzzle = the NPC model's own blast joint.
- No long-idle fidgets: Jak's random idle variations look wrong on another body.
- **Check an NPC clip's data before using it as an idle** (glb from the ripper: keys, duration, per-bone
  rotation/translation/scale range). Sig's `sig-highres-idle` is ONE key (a cutscene base pose: he stood
  frozen, "a T-pose"); his `idle-wasdoors` is the real one (11 s, weight shift). Ashelin's `idle0` is an AI
  combat-ready loop (0.93 s, body rocking 7 cm, chest scale 0.93-1.20) that looks like heavy deformation under a
  close player camera: play it slower (0.6) and keep ~40% of the motion away from its first frame (lerp each
  joint's local, parents first, eyes excluded). Measure in game with a watcher (joint row lengths and offset
  from the root, min/max over 2-3 s) before and after.
- A clip that holds a prop in one hand: give the free hand's arm to the other side mirrored. Jak 3 rigs mirror
  across x (left quaternion x y z w, right x -y -z w), so right local = S left local S (negate row 0's y,z,
  rows 1-2's x, trans x); pair the joints by their order in each arm's chain.
- Writing bone matrices by hand: zero each row's w (and trans w = 1) after lerping locals. Garbage row w's
  exploded the next frame's 4x4 inverses (main joint scaled by 9e6). Never invert a prejoint bone (not a
  real matrix): take main against the root (joint 0) instead.
- A stylised walk clip (Sig's museum walk swings each arm to shoulder height) can be calmed by blending both
  arms' locals part way (~0.5) toward a hanging-arm pose while walking unarmed; also on Jak's retargeted run.
- A big skin with no run clip of its own (Sig: only `sig-highres-sig-walk` exists) on Jak's retargeted run
  looks crouched and wide-legged: Jak's knees are bent for his own height. Fade in by speed (top walk speed to
  +3 m/s), raise main/hips (Sig 0.35 m), move the IK foot targets ~30% toward the midline and scale the foot
  lift down (~0.45). Measure it numerically, not by eye: leg extension (hip-ankle / thigh+shin) and ankle
  spread / hip width, averaged over 150 frames at full speed on open sand (teleport there; near walls the run
  stalls at 1-2 m/s). Sig 0.77 -> 0.88 extension (Jak 0.74), spread 0.85 -> 0.71.
- release_gate.ps1 with a single instance (`-FirstInstance 19 -LastInstance 19`) runs only one row per call
  (it never frees the instance): loop over rows. Stop your own dev goalc first, it holds the nREPL port.
- A fresh worktree for goalc needs: `goal_src/user/user.txt` + `goal_src/user/enhanced/` copied (jak3 ->
  jak3_pal), junctions for `iso_data/jak3/*`, `iso_data/jak3_pal`, `decompiler_out/jak3[_pal]`,
  `out/enhanced`, hardlinked fr3, and copies (not links) of `out/jak3/iso` and `obj` that goalc writes.
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
- **A new move with no clip anywhere (Ashelin's front kick):** key it in GOAL on top of the skin's idle,
  not via build-actor. Per bone, a target direction (bone -> child joint) in model space (+z forward,
  +y up, -x right) for each key pose, lerped by phase; turn the bone and everything under it about the
  joint with `quaternion-from-two-vectors-partial!` + `quaternion->matrix` + `vector-rotate*!` on the
  rows and on (trans - pivot). Independent of the rig's local axes; parents first. Check numerically
  (dir dots with fwd/up) before trusting a 640x360 screenshot: an elevated camera made a vertical shin
  look diagonal.
- Swap one of Jak's attacks for a character: in the vanilla state's `:enter`, `(go <new-state>)` when
  `next-state` is still the vanilla one (as darkjak does), and reuse its `:event/:enter/:exit/:trans`.
  Hit window = `target-danger-set! 'punch` on/off by phase (same damage); put collision-spheres 6 on the
  skin's foot: transform-index -2 is an UNROTATED world offset from control trans; zero sphere 7 (Jak's
  hidden forearm). The skin poses a frame after the target: measure the pose one frame later.
- Screenshots of a fast move: a REPL-set freeze global that holds the phase (pose and hit sphere).
- A character's own magazine on Jak's gun HUD: `sv-72` (max) and `values 1` from hooks; the shells and
  "n/max" then draw as for Jak's guns.
- Mocap from markers only (ACCAD C3D, CC BY 3.0, Z up, mm, 120 Hz, DEC floats: swap 16-bit words, /4):
  a ~100-line pure-Python C3D reader is enough (no Blender). Joint centres: hips = pelvis centre + 0.7 of
  half-width - 8 cm down; knee/ankle markers moved ~4 cm medially; shoulder marker 5 cm down. Store per
  sample bone directions + pelvis up/forward + height fraction in the kicker's model frame (left = up x
  forward) as a GOAL static float table; feed the same bone-aiming code. Commit only the derived table,
  with attribution. A real front kick peaks at ~0.75 of head height, not at the head.
- goalc for Jak Enhanced needs `--user-auto` (jak3 maps to jak3_pal); `dev_goalc.ps1 -Instance n`
  already passes it. Headless gk (~240 MB) is enough for skeleton/state measurements when RAM is tight.
- **Headless gk stalls STR streaming** (cutscene clips, streamed ambients): the log stops after
  "STR_RPC for ... chunk" and check-busy never clears. Anything streamed needs a windowed (minimized) gk.
- **Finding an NPC's own pose for a hold (Sig two-handed):** play each of its cutscene STR clips frame by
  frame in the skin and score each frame numerically (hand-to-barrel segment distance, barrel level,
  barrel vs chest facing); log best frame and good ranges per chunk, then capture the joint quaternions of
  one frame into a static table (hold-local). Apply them, then turn both shoulder subtrees together so the
  barrel points along the shot, and close each arm back to its shoulder with two-bone IK keeping the hand
  turn. Check "gun-along-shot" dot ~1.0 in the log.
- **Walk speed of an NPC clip: measure, don't guess.** Log the planted foot's ground slide (lowest foot
  within 12 cm of the ground) against Jak's speed at a few speeds; the speed where slide ~0 is walk-speed
  at rate 1 (Sig: 3.05 m/s, not 2.0; slide 1.3-1.75 -> 0.12-0.27 m/s). Let a long-legged skin's rate go
  down to ~0.45 or its feet slide when slow.
- **Sized skin on Jak's run: leg IK.** Scaled up, Jak's pose leaves the feet floating (never within 12 cm
  of the ground). Target each ankle at Jak's ankle offset from his prejoint: forward component unscaled
  (stride must match Jak's real speed), sideways scaled, height = skin's bind ankle height + size x (Jak's
  ankle height - his bind ankle height); two-bone IK on thigh/knee, keep the foot's turn.
- **Punch/kick with an NPC gun out:** fade the gun-hold overlay out (fast in, slow out, also 0.15 s past
  the attack end) so Jak's attack arms show; keep the gun matrix at the grip in the right hand.
- **Shots from a borrowed muzzle with no target:** aim along `(-> *target* gun fire-dir-out)`, not toward a
  point ahead of Jak's hidden hand (that climbed ~6 deg).
- REPL tricks: hot reload re-runs top-level `define`s (globals reset: respawn the skin after it); a
  changed function signature won't hot-load ("Typecheck failed": rename it); a pad-engine connection keeps
  the old function pointer; `format` takes at most 8 args incl. dest and string (split it); an undefined
  symbol anywhere fails the whole eval form. Restart the dev goalc when game.gp gains a file ("No rule to
  make ..."). After a goalc restart run `(lt "127.0.0.1" <port>)` if evals say "generated code, but
  wasn't supposed to". A temporary scan function calling a helper defined further down compiles only by
  hot load, not in `(mi)`: remove test code before the build.
- To see a frame where numbers look wrong (Jak's node-list 1.9-3.5 m off control trans for ~5 frames at a
  walk start), a watcher child calls `(set-master-mode 'freeze)` on the condition and you screenshot the
  frozen frame: Jak was drawn centred, so it was data only.
- **Verifying a playable NPC from the REPL (no repo edits):** switch character at runtime by redefining
  `(defun enhanced-player-name () *my-name*)` (the C++ menu answer wins over the env buffer, so writing the
  buffer does nothing); measure with a `process-spawn-function` watcher in `*display-pool*` gated by a global
  (kill it later by pid via `iterate-process-tree`). An env test step (`*enhanced-sig-gun-test*`) rewrites
  the pad globals every frame: set it to #f before driving `*enhanced-pad-lefty*`/`hold` yourself.
- **Foot-slide numbers need Jak's baseline under the same metric.** "Lowest ankle within bind height +
  6 cm, same foot as last frame, xz speed" gives Jak himself 0.7-1.06 m/s walking and ~1.2 running, so a
  skin's 0.8-1.0 walk is Jak-level, not "0.12" or "bad". Main-joint xz jump per frame (main - control
  trans): walking ~0.01 m; Jak's own running attacks reach 1.3 m (prejoint data), a prejoint-placed skin
  0.1-0.45 m.
- **Scripted pad input must update `cpad change-time`** (as `service-cpads` does for a real pad), or the
  game thinks nobody touched the pad: `target-gun-stance` puts the gun away via `can-play-stance-amibent?`
  (30 s without input + 30 s since the last ambient), which looked like "the gun goes away by itself
  ~13 s after the last shot" and made a scripted "D-pad right = put away" bring it OUT. Fixed in
  `enhanced-test-pad` (drawable.gc); still read `using-gun?` before toggling. Stick input into water
  (`target-swim-stance`) also drops the gun: pick a dry test spot (ctygenb-start has water nearby).
- Spawning a traffic type whose code/art isn't loaded crashes gk (0xC0000005 in GOAL): `citizen-spawn`
  takes the type from `type-from-traffic-object-type`, unbound when its level is out (roboguard-city lives
  in a mission level, not ctygenb). Check `(art-group-get-by-name *level* "skel-<name>" #f)` first. The
  city's own population (flitters, guards, citizens) is enough to test shots: windowed only (headless:
  census 0). A level's start can reset `*game-info* features`: re-lend a lent gun, log it once.
- **Foot lock for a skin on Jak's pose:** Jak's prejoint runs up to 0.9 m ahead of his root in the run
  (and more with the gun out), so ankles taken against it slide ~2 m/s. Per leg: when Jak's ankle comes
  within 5 cm of its bind height (on-surface, not attacking) store the IK target's world xz; hold it
  while down, let go past 0.4 m from the unlocked target, fade out in 0.1 s. Sig: run slide 1.17 vs Jak's
  1.76, gun run 0.85 vs 4.10 (same run). Measure with a `*display-pool*` watcher that drives phases
  (lefty 0 run / 90 walk / 128 stop: -1 leaves the stick where it was) and counts only the lowest ankle
  within bind height + 6 cm; run-to-run noise is ~±1 m/s (terrain), so compare inside one run.
- **Sig's arms in Jak's pose were crossed** (each hand past the other shoulder, above the chest; standing
  and walking, long before anyone noticed: a 55% row lerp toward his idle hid it). Measure hands against
  the skin's own shoulder axis, next to Jak's own hands (`(-> *target* node-list)` 19/28 vs 17/26), with
  `*enhanced-player-retarget* 'all` to force Jak's pose. Fix: keep the skin's own clip arms under Jak's
  pose (Jak's only in attacks). Even then a stylised NPC clip's arms may be wrong (Sig's museum walk holds
  the right arm bent forward, hands still): drive the arms procedurally by direction (shortest turns of
  the upper arm and forearm subtrees, `turn-tree`): hang at the side, swing opposite to the legs phased by
  the *difference* of the two ankles' forward offsets from their hips (one leg alone: lean and bent knees
  pushed both arms forward), elbow bend more when running. Never mix local turns between far-apart poses:
  row lerp shears, slerp crossed the arms.
- **Cloth joints parented to the thighs (skirt panels)**: holding the panel tops toward the hips on a
  retargeted run lets the knees through; keep each chain top on its thigh, damp only the lower joints
  toward their bind turns (the clip's out-of-step cloth swing).
- A REPL watcher's `format 0` lines can lag tens of seconds behind in the gk log under GL warning spam;
  and a teleport to `*enhanced-hellcat-spot*` outside the run test lands in the sea (swim states keep
  pose-blend 1): check `(-> *target* state name)` first, or measure through the gate row instead.
- Hot-load pitfalls: dev_reload says NEEDS "type definition changed" for any file with a deftype (use
  `-Force` when the type is unchanged); a `define-extern` must match the defun's inferred return type
  (`or` -> `object`, not `symbol`); after a temporary (ml) of an edited copy, restore the source and
  **touch it** before `(mi)`, or the newer .o keeps the test code in the CGO. A restarted gk needs
  `(lt "127.0.0.1" <port>)` before evals ("generated code, but wasn't supposed to").

- **Retargeting arms: compare the two rigs' bind poses first.** "His turn from his bind pose, put on its
  bind pose" only works when both are bound the same way. Jak is bound in a T (upper arm along x), Sig with
  his arms hanging (0.03 -0.92 -0.37): every arm bone ended a quarter turn off Jak's (dot of the two bone
  directions 0.03 in a punch, fists crossed at the chest). Fix: per bone, the shortest turn from the skin's
  bind direction (child joint - joint, model space) to Jak's, put between the skin's bind matrix and Jak's
  skinning matrix (`bind-world * C * (jak-bind-inverse * jak-bone)`); the hand takes its forearm's. Dot
  0.99-1.00 in every attack. Measure with a `*display-pool*` watcher: dot of (elbow - shoulder) and
  (hand - elbow) between Jak's node-list and the skin's, per frame, min over the frames at full weight.
- Blend a limb between two far-apart poses by turning (slerp of the joint's matrix, own row lengths and
  translation kept), parents first, never by blended rows. Seek the blend weight **before** the retarget
  reads it, and scale every later overlay (rest pose, walk arms, gun hold) by `1 - attack weight`: left to
  their own 0.2 s seeks they held one arm back for most of a 0.3 s punch.
- Fists for a skin whose clips leave the hands open: capture the finger joints' locals (joint to parent)
  from a clip where the hand grips something (Sig's gun hand in his armed idle), mirror them for the other
  hand, slerp the fingers' locals toward them by the attack weight inside the retarget.
- Jak's attack list for a skin: `target-attack`, `-running-attack`, `-attack-air`, `-attack-uppercut(-jump)`,
  `target-flop` and `target-flop-hit-ground` (the dive was forgotten: arms hung through it). With a gun out
  `target-running-attack` is a gun swing (frames 0-4.7 at half rate, peak 3.7; bare punch: windup 2.8,
  strike 5.7 of 9.5). Jak's punch scales his fist (hand 1.3-2 m from his chest): don't copy the scale.
- Before/after shots of a fast move in ONE boot: a watcher freezes (`set-master-mode 'freeze`) when the
  state name and `skel root-channel 0 frame-num` reach set values; toggle the fix from the REPL (identity
  matrices = old path); Jak himself as the reference by redefining `enhanced-player-name` to "jak". Turn
  the camera to a front three-quarter view by holding the right stick until
  dot(Jak forward, camera forward) is about -0.6, again before each shot (it swings back behind him).
  A two-button move in the air (jump, then square 14 frames later) needs an in-game sequencer: two REPL
  calls are ~0.5 s apart and he has landed.

### New attack moves for a playable NPC from generated motion clips (Jak 3 Ashelin, Sig; Nov 2026)

- **Measure a generated clip before building on it.** Higgsfield Kimodo `.npz` (27-joint `cskel27`, 20 fps,
  Y up, +x left, +z forward; `posed_joints`, `global_rot_mats`, `smooth_root_pos`, `foot_contacts`; numpy
  reads it, `allow_pickle=False`): per frame, the striking joint against the hips (reach, height), elbow/knee
  angles, pelvis yaw, feet speed while `foot_contacts` says down; plus stick-figure contact sheets drawn with
  PIL (side, front, top; right side red, left blue), ~1 k tokens a sheet. Of 17 takes of 1.6 s, 16 stood in
  guard for 1-1.4 s and most ended before the strike (two pistol-whip takes and two spin takes held no
  strike at all; "elbow" never brought the elbow in front). Ask for one action per take, 2.5-3 s, the strike
  in the middle; say in the report which moves are clip motion and which are posed.
- **Store a move as rig-independent vectors, not joint rotations.** 30 samples a second, model space: pelvis,
  chest and head as up + forward, each limb bone's direction, each hand's line plus its thumb side, the
  pelvis's sway from the root and the lowest ankle's height (both in hip heights), a gun's barrel. The same
  table then drives rigs with different bind poses and proportions (Ashelin T-pose, Sig arms hanging, his
  ankle joint 0.37 m up), and it is derived from original motion only, so it can be committed.
- **Author on a timeline, clips as pose sources.** Key poses = clip frames edited by a few operators on joint
  positions (aim a bone, twist/lean the chest, plant the feet and move the pelvis with two-bone IK, put a
  hand somewhere), eased per segment: anticipation at 0.09 s (ease out), strike at 0.19 s (`u^3.5`, arrives
  fast), a hold with a spring past the pose along the way it arrived (`exp(-4.5u) sin(2 pi 1.15 u)`, 8-10 %),
  recovery to 0.64 s. A 360 degree spin: a key every ~70 degrees (shortest-arc blends between keys), about a
  point a third of the way to the pivot foot (on the foot itself the body swung 0.4 m out and back).
- **Keep the hidden player's own attack state**; only the drawn pose changes (physics, momentum, hit spheres,
  sounds and combos stay vanilla). Start a move when Jak's state name is the attack and his `state-time`
  differs from the one the last move started for; play it past the state's end (the punch state is 21
  frames) as the recovery; drop it when Jak's state is not stance/walk/attack.
- **Turn a joint whole from up + forward:** tilt by the shortest turn of the model's up (second row of
  bind-pose x bone, the skinning matrix), then twist about up by `atan` of the two flattened forwards; build
  that turn with `quaternion-vector-angle!` and check its sense by turning the vector and comparing (no
  guessing the engine's handedness; exact at 180 degrees, where a shortest turn picks any axis). Same twist
  for a hand about its own line, from its thumb joint.
- **Ground a table pose by the lowest ankle**, not by the pelvis height: after aiming, move the whole body up
  or down until the lowest ankle is as high over its bind height as the table says (0 = a foot down).
- **Bring a move in, and cut it short, by crossfading from the pose last drawn**: keep every frame's final
  bones (place taken from the root), freeze a copy when the crossfade starts, slerp each joint from it over
  0.08 s (0.17 s into a walk). The move itself always runs at full weight on the idle. Blending a move in by
  weight over whatever was under it (Jak's run pose with leg IK and a run lift) gave pops of 65/69/218/349 cm
  (main/head/hands/feet, second differences), a foot 44 cm under ground and skew 0.51; with the crossfade
  13/17/57/30, 0 cm, 0.00.
- **A blend helper that lerps matrix rows shears whenever its weight is partial and the poses are far
  apart** (her clip's raised gun arm against Jak's punch: skew 0.95). Fix it once inside the helper (rows
  normalized, `matrix->quaternion`, `quaternion-slerp!`, row lengths put back, place lerped; plain rows when
  the weight is 0 or 1 or a row is empty), not call site by call site.
- **A correction weighted by "Jak's state is his walk" snaps**: Sig's run lift (35 cm) vanished in the frame
  a run ended (stop, jump, attack): body, hands and feet popped with it. Ease such a weight once a frame.
- A surface flag meant for Jak's gun can hit the character's own: the punch surface's `gun-inactive` put
  Ashelin's pistol away as she struck with it. Allow it while the surface also has `attack`; block firing.
- **A long gun in both hands during a move:** gun at the right hand's grip, the hand (fingers, gun, muzzle)
  turned until the barrel lies along the table's barrel (grip hand to fore hand in the clip), then the left
  arm by two-bone IK to a point fixed in the gun's own space. Measure that point in the game from the
  existing two-handed hold: left hand through the inverse gun matrix (Sig: 425 455 2300 units).
- **A review watcher** (repo `scripts/enhanced/chars_review`): one log line per state of Jak with the skin
  against Jak: lowest ankle against its bind height on the ground (min/mean), planted-foot slide, second
  differences of main/head/hands/feet (a joint that jumps), shortest and longest matrix row and skew
  (sheared bones), limb directions against Jak's, a hand's distance to the spine, and in a vehicle hands,
  feet, head and hips against Jak's; `POP` lines for single frames; a pad sequencer `(ca-q frame op arg)` so
  a two-button move is frame exact. Jak's own feet are no baseline: his leg IK keeps them off his prejoint
  (their pops against it read 3-7 m).
- Traps: `sed -i` in Git Bash rewrites a CRLF `.gc` as LF (patch scripts then stop matching: normalize, write
  CRLF); a heredoc with an odd number of apostrophes breaks the Bash tool (write the script with the file
  tool); `powershell.exe` started from a Bash script failed with fork errors when RAM was short (launch from
  the PowerShell tool); a launcher that writes "the gk I started" to a pid file is overwritten when the user
  runs the same launcher, so a restart script would kill the USER's game: keep your own pid elsewhere and
  compare the start time; and never `(lt)` while a gk you did not start holds the instance's port.

## A crash with no GOAL error: reading the minidump (lesson, Jak Enhanced)

- **0xC0000094 (integer divide by zero) in module `unknown` is usually `(break!)` = `(/ 0 0)`**, not a real
  division. The commonest one: `enter-state` with a zero `next-state`, i.e. `(go <state>)` on a state that
  is not defined (code of a level that is out, or a leftover from an earlier game). Don't hunt for integer
  divisions in the feature code.
- Read it from the WER minidump (`%LOCALAPPDATA%\CrashDumps\gk.exe.<pid>.dmp`) with ~60 lines of Python:
  exception stream 6 -> x64 context (registers from +0x78: rax rcx rdx rbx rsp rbp rsi rdi r8-r15 rip).
  **r15 = GOAL memory base, r14 = symbol table (#f), r13 = the running process**; `rip - r15` is the GOAL
  address. The dump holds 256 bytes around rip and nothing else of GOAL memory (no stack, no process): a
  `04 fe 15 00` type tag marks the function's start; `xor rax,rax / xor r9,r9 / cdq / idiv r9d` after a
  test of `[r15+r13+0x44]` (process next-state) is enter-state's check.
- Engine code and the kernel's pools load at the same GOAL address every boot of a build: the event's
  offset low bits (`...ff3f`) are the same crash across runs and days, and r13 names the process: print
  `*target*` in any boot (`#x1d1e84` = the target). Then list the undefined states from the REPL: for each
  `(go target-...)` in the source, `(zero? (the-as int (-> 'name value)))`. Jak 3 at ctyport: flut, indax,
  mech, tube, turret, ladder (level code), plus leftovers nothing defines: `target-carry-pickup`,
  `target-ice-stance`, `target-yellow-jump-blast`, `target-racing-start`.
- The bug found this way: a test unlock set every `game-feature` bit from 5 up; bit 19 is Jak 2's carry,
  and with it R1 in `target-stance`/`target-walk` does `(go target-carry-pickup)`. Jak took his gun out
  first; a playable NPC keeps Jak's gun away, so its first shot killed the game. Unlock named features
  only, and guard a vanilla `go` to a state the game doesn't have with `(nonzero? <state>)` (saves made
  while unlocked keep the bit). Unnamed bits that are real: 21/22 gun upgrades, 31-35 city passes, 36
  board training.
- Headless repro (`--no-display`, 240 MB, boots in 2 s at desert-start; at ctyport-start the target stays in
  `target-continue`): scripted pad press, then `tasklist` for the pid and event 1000 for the same offset.
- Tooling traps hit on the way: a goalc killed while connected leaves that gk's listener stuck ("Failed to
  get version number" on the next `(lt)`): restart the gk. A restarted goalc no longer knows globals you
  defined from the REPL (re-send the watcher after a fresh boot), and a running goalc refuses a deftype
  whose layout changed ("is redefined as"): restart it. PowerShell turns `3.0` into `3` inside a string
  (GOAL: int given for a float, the whole form fails silently if you drop the output) and strips inner
  double quotes passed to a native exe (`"jak"` became a symbol): keep frames as strings, send quoted
  forms from bash. Another agent's cleanup can stop your daemon: when evals refuse to connect, check the
  control port before blaming the game.

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
- **A worktree with its own changes runs on its own data, not the main tree's** (Nov 2026): worktrees that
  junction `out\jak3\iso` to main share one set of CGO/DGO, and any agent's `(mi)` rewrites it; a gk from
  another commit then dies ~60 s into boot right after `[enhanced] population 0` (0xC0000005, module
  `unknown`), even main's own gk. Give the worktree a real `out\jak3\iso` (robocopy main's, 4.4 GB: it also
  holds STR/SBK/text the build doesn't make), `iso_data\jak3_pal` and `iso_data\jak3\*` junctions (the
  custom-level step reads `iso_data/jak3/CGO`), `goal_src\user` copied, then
  `goalc --user-auto --game jak3 --proj-path <wt> --cmd "(mi)"` with `JAK_ENHANCED_INSTANCE` set (else it
  opens instance 0's nREPL port). Run gk with `--proj-path <wt>` and junction what's read at run time:
  `out\jak3\fr3`, `out\enhanced`, `decompiler_out`, `local\editor-kit`, `custom_assets\jak3\texture_*`,
  hard links for the ignored `custom_assets\jak3\scenery\game_*` files. Logs land in `<wt>\log`.
- **Naming a crash inside gk.exe without a PDB**: a Release gk has no symbols, but a mips2c function is
  registered by name. Find the function start before the fault (`llvm-objdump -d` back to the last
  `int3`/`ret`), grep the whole disassembly for `# 0x<start>` (a `lea` into the registration call) and
  read the string the `vmovups`/`movabsq` just before it build (`sp-launch-particles-var`). Code like
  `movslq 0x8(%rax,%rcx)` with `rax` loaded from a global is GOAL memory: a bad GOAL pointer.
- Capacity (RTX 5070 Laptop, Ryzen AI 9 365, 32 GB, jak3 desert-start, Performance, 640x360): each gk
  ~2.8 GB peak working set; 2-4 instances all held ~50-58 fps, 4 left 0.5 GB available RAM, so 3 is
  the default max. RAM, not GPU, is the limit. Script: `scripts/enhanced/multi_run.ps1`.

## An Enhanced vs vanilla screenshot tour (lesson, Jak Enhanced)

- Vanilla look = `JAK_ENHANCED=0` (same flag as the menu's "Enhanced graphics (all)"; replaced scenery and
  HD textures may still load). One windowed boot per spot and mode: `dev_launch.ps1 -Instance 19 -TestCfg
  -Width 960 -Height 540 -Start <cp> -NoGoalc -NoShaderReload -Wait -Env @{...}`, settle 12 s, `capture_window.ps1
  -ProcessId <pid>`, `Stop-Process` that PID: ~29 s per shot, 24 shots in 12 min with one instance.
- Teleport tests (Jak Enhanced gfx-tech2): `JAK_ENHANCED_TP` fires at camlog frame 90, often before the boot's
  own continue, which then puts Jak back at the start (the `[camera]` lines return to the start spot). Teleport
  late with `JAK_ENHANCED_MENU_SCRIPT=22:3:x/y/z` (`/` stands for `,` in a script value). A spot from the sky
  map's roofed-floor finder can be a false floor: Jak falls and respawns at the start, so check the last
  `[camera]` line before trusting a shot. Quick roofed spot that boots directly: `waspala-start` (palace hall).
- Hour: `JAK_ENHANCED_HOUR=<h>`, **not** `JAK_ENHANCED_MENU=1:<h>`: any `JAK_ENHANCED_MENU` value also opens
- The game clock runs on (~1 game hour per real minute): a boot at 17h is night 5 min later, so A/B pairs taken  minutes apart differ by the hour. Hold it with repeated menu-script hour steps, e.g. `20:1:17.5,35:1:17.5,...`  (no step limit), then switch blocks (`310:1:22,...`, `490:1:12,...`) for a noon/dusk/night tour in one boot.
  the menu over half the frame. Clear sky: `JAK_ENHANCED_WEATHER_SCRIPT=0:0`. Quality: `JAK_ENHANCED_PRESET=2`.
- Spots that boot directly: `desert-start`, `wascitya-start` (Spargus), `waspala-start` (palace), `ctyport-start`,
  `ctysluma-alley`, `game-start` (arena); Hellcat in flight = `JAK_ENHANCED_HELLCAT_TEST=1`, shoot on the
  `[hellcat-test] "firing"` log line; characters = `JAK_ENHANCED_PLAYER=jak|ashelin|sig` at desert-start, then
  crop around the character (no camera-distance switch exists).
- Jak Enhanced Hellcat test (gfx-polish, Nov 2026): the log has no `"firing"` line any more, only `[hellcat-test] diving|low|out|parked ... shots N`: wait for `shots [1-9]` instead, or a capture loop never fires.
- A ground fix keyed only on the hour (a `golden`-weighted floor under sand/rock for one dark desert slope) also lifts every *cast* shadow on sand: Spargus' streets at 18h went 2x brighter and the paving stones stood out flat navy. Check such fixes at a second spot with walls (Spargus 18h) before calling them done; in `enh_composite.frag` the surface normal `nn` is not in scope at the end of `main()`, gate by a value computed earlier.
- Main-vs-branch baseline without touching the main tree (gfx-polish final verify): copy main's `out\build\Release\bin` to scratch, and build a scratch proj dir that mirrors the worktree with junctions (`mklink /J` dirs, `/H` files) except `game\graphics\opengl_renderer\shaders`, filled by `git archive main <that dir> | tar -x`. Both gk then share the worktree's `out\jak3`, tuning and log dir (logs: pick by creation time); valid while the branch changes only C++ and shaders (`git diff --name-only main..branch`). `JAK_ENHANCED_HELLCAT_TEST=1` needs `JAK_ENHANCED_START=desert-start`: without it the test boot lands in ctyport and never logs `[hellcat-test]`.
- Main-vs-branch fps (gfx-polish final verify r2): capped runs lie for main. Before the branch's `glFlush` fix, main's "GPU ms" and the `tail-span` pass include the limiter's idle (GPU 15.5 ms, tail-span 8.8 ms at 60 fps), so capped GPU/post numbers look 3x worse than the branch. Compare with `JAK_ENHANCED_UNCAPPED=1` on both (main has it; `JAK_ENHANCED_TEST_RES` is branch-only) and read `renderer ms/frame` (CPU) apart from `GPU ms`: Spargus 18h 247 vs 198 fps came from renderer CPU 3.24 -> 4.19 ms, while the post passes moved only +0.3 ms.
- A lane re-enabling a default that main switched off on purpose is the first suspect for "nights darker": `git log main -G '<uniform> = 0\.0' -- <shader>` finds main's reason. Slums 22h: tune_night_pale back on = 31.8 vs 40.0 luma. Compare night shots only on the same boot path: desert 22h reached by a menu-script hour step from 12h read 15% darker than a direct `JAK_ENHANCED_HOUR=22` boot of the same build.
- PowerShell: a `[string]$Rows` param passed `-Rows a,b,c` unquoted arrives as "a b c" (array joined by spaces), so `.Split(',')` matches nothing and the script silently runs zero rows: quote list arguments.- Hellcat ground shadow (gfx-polish r10): at noon `g_enhanced_casters.cast` skips the game's Shadow2 entirely, so a grey patch under the Hellcat is the composite's sun-map shade, not Shadow2 (a Shadow2 change showed no difference). The desert's lilac shade tint (1.15/0.85/0.3) turned near caster shadows on sand blue-grey; `tune_shade_hue` pulls it to neutral on saturated ground within 30-80 m. `JAK_ENHANCED_HELLCAT_TEST=1`: the low dive passes last ~20 s after the first `diving` line, then `parked`/`end`: start the A/B right at `diving`, 1.1 s settle per tuning flip. Burst folders named by tag are reused across boots: sort shots by LastWriteTime (or clear the folder), or an old boot's frame gets paired.
- Fire/glow triage (gfx-polish r11): `tune_fx_debug 9` = r flame_keep, g fx weight, b fx_day. Palace braziers: flame_keep 0, halo weight set by drifting smoke wisps (dust mark): frame-to-frame noise swamps any single A/B pair, so measure a mean over 6+ frames per variant before you keep a change (a glow-alpha lift moved it 0.090 -> 0.092: reverted). Check the claimed load-in glitch still exists before fixing it: a 0.6 s burst from launch showed Spargus' orange veil (G2) already gone after the eye-adaptation black-frame hold.
- `cmake --build out\build\Release` from a plain shell fails (`'algorithm' file not found`: no vcvars); build with `scripts\enhanced\dev_build.ps1 -Repo <wt> -Targets gk`.
- Branch-vs-main tour: a hue shift is not a regression until vanilla (`JAK_ENHANCED=0`) is shot at the same spot and hour. Desert-start at hour 17.5 the branch's ground went olive (52,56,41 vs main 80,64,48); vanilla there is green itself (65,78,50), and the "game's moonlit hue" step was following it. Also: a test launcher with a `[switch]$Main` param and a `$main` path variable breaks (PowerShell names are case-insensitive): name the switch `-UseMain`.
- **Several spots and hours in ONE boot** (scouting): `JAK_ENHANCED_MENU_SCRIPT=<s>:<kind>:<value>,...` (kind 1 =
  hour, kind 2 = continue point, e.g. `1:1:12,45:1:18.5,75:2:wascitya-start,78:1:12,...`; it doesn't open the
  menu). Each step logs `[enhanced] menu script`: capture N s after the Nth logged step (hour ~12 s, travel
  ~40 s). 6 shots / 3 spots / 4.5 min. A worktree has no `out\jak3`, so dev_launch always runs `--proj-path`
  of the main tree; a no-edit scout at the main tree's commit can reuse its bin. To scout a worktree's own build, skip dev_launch: copy `<wt>\out\build\Release\bin` to a scratch bin and start gk with `--proj-path <wt>` (the worktree has `out\jak3` once built), the testcfg copied as dev_launch does, and the menu script; logs then land in `<wt>\log`. A Enhanced boot and a `JAK_ENHANCED=0` boot with the same script give same-spot vanilla pairs (~4 min each). 640x360 shots downscaled
  in the viewer show fake vertical stripes at night: zoom a crop before calling it a glitch.
- A tour that re-copies the bin before each boot fails on the next row ("file in use" on gk.exe) when the
  killed gk has not exited yet: wait on `$p.WaitForExit(10000)` after `Stop-Process`, or copy once. The build
  hash printed bottom-left of every frame tells which commit the gk was built at: check it against
  `git log` before trusting a "fixed in C++" claim (shaders hot-reload from source, the C++ does not).
- Glitch-hunt scouting that worked (gfx-polish, Nov 2026): capture the window every 2.5 s for the whole menu-script
  run (~170 frames / 8 min), then pick frames per segment into contact sheets (4 x 360 px) and run a numpy
  32x32-block diff of consecutive frames to spot flicker/pops without viewing them all. Pair Enhanced vs
  `JAK_ENHANCED=0` by the logged `menu script <t> s` times, not wall time: vanilla boots ~2 s sooner and its
  hour change lands later, so the "same" second shows another hour or a black load frame. `wasall-start`
  lands on desert-start; `ctyinda-start` requested from `mhcityb` (Metal Head tower) did not travel.
  `JAK_ENHANCED_PLAYER=ashelin` in the same run covers a character at every spot.
  Also: `ctyport-start` requested from `ctysluma` did not travel either (log keeps saying `in ctysluma`):
  check the `in <level>` of each logged step before reading a segment as the new spot. Grey smoke strands
  drifting through the Spargus palace hall are vanilla (seen with `JAK_ENHANCED=0`), not leaked dust. Live
  tuning keys (e.g. `weather.test_spell` 5 = sandstorm, -1 off) can be flipped mid-run by rewriting
  `local\tuning_i<n>.json`: force the storm for the town-dust check, then clear it before the next spot.
- Rule out before you fix (gfx-polish r7, Spargus palace 18h lime-yellow blob): count the glitch's pixels
  per frame (a colour mask over a burst of frames, numpy) and A/B suspects with live tuning keys in one run
  before writing a fix. Capping the smoke sprites' lamp tint changed nothing (reverted), `post.glow_soft` 0/1
  neither, and composite embers are 3.5 px at most: the blob is something else (next: a
  `JAK_ENHANCED_FX_DEBUG` boot at waspala). Travel misses: `towera-start` requested from `waspala` lands in
  `mhcityb`, and `desert-start` from `mhcityb` doesn't travel at all. A Spargus boot in clear weather
  showed no orange load-in veil (needs the desert dust alive).
- PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM: a commit message file made that way puts
  `U+FEFF` at the start of the subject. Write it with `[IO.File]::WriteAllText` (no BOM).
- Own capture loop for a worktree build: a script run via `[scriptblock]::Create(ReadAllText)` has an empty `$PSScriptRoot` (pass the dir as a param); frame names written with `'{0:000.0}' -f` get the Italian locale's comma (`039,9.png`), so parse with `replace(',', '.')`. Desert dust can stay alive after travel (`rogue level entity desert-dust-storm still alive` in the log): Spargus at noon then shows an orange veil that vanilla doesn't have, check this line before blaming a haze change.
- Improvement scouts: grep `enh_composite.frag` (~5000 lines) before proposing "add X". Already there by round 5:
  hot air + embers over fires (`fire` uniform), light flicker, SSR + RT reflections, caustics, shore foam and
  wakes, cloud shadows, PCSS, eye adaptation, CAS sharpen, rain puddles, material classes. Real gaps are
  usually in the *connections* (water vs floating objects, sky outside the desert zones), not missing effects.
- The testcfg (`-debug`) keeps the ImGui toolbar strip and "outside of bsp" text in every shot: same on both
  sides, ignore. Fights (slums) and particles are not deterministic between boots: don't call an enemy or
  spark "missing" from one pair.
- Second-opinion pass: re-look at every pair yourself; one contact sheet (2 pairs per row at 796 px, PIL,
  caption per tile coloured by severity, `[D]` for issues another workflow owns) reads faster than 12 files.
  Ground darker than vanilla with **bright outlines around decals/slabs** = ground receives a shadow (or tint)
  the decal layer does not: toggle shadows on that spot before calling it a material bug.

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
  Also needed (fresh worktree, measured 87 s `(mi)`): junction `decompiler_out\jak3_pal` (else "tpage-dir.txt
  does not exist"), `iso_data\jak3\<CGO,DGO,...,VAG>` dirs, `custom_assets\jak3\<merc_replacements,
  texture_*>` and `out\enhanced`. Hardlinked fr3 files are safe: `(mi)` writes new files (custom levels
  came out with 1 link), it never writes through into the main tree.
- **Headless rows in parallel (gate v2):** rows that only read log lines run `gk --no-display` (~240 MB,
  4 at once beside 1 windowed). Headless has no renderer, so anything driven from the renderer's frame
  (env test switches read in a post-process update, fps lines) does nothing: move such switches to the
  game thread (a kernel function GOAL calls every frame, e.g. `pc-enhanced-set-scene`) and give headless
  a frames line of its own (`[camera] ... in <level>` every 2 s). **A headless gk can't change level**:
  boot levels load, but a level asked mid-run logs "Adding level X" and never finishes (Spargus gate,
  continue to another level, air train: actors missing too). Those rows stay windowed.
- `goalc --cmd "(mi)"` needs `--game jak3` too, else it builds Jak 1 ("iso_data/jak1/... does not exist").
- End a row early once every check holds for ~8 s (expect lines, levels, shots, frames lines scaled to
  the time run): 25 rows went from ~40 min to 15 min (15 windowed + 10 headless). Put values in the regexes
  (`(?<v>[\d.]+)`) with ranges, and print every matched check with its value in the PASS line.
- A per-frame "body jump" metric (drawn main joint minus its root, xz, max per phase) is meaningful for
  skins only: Jak's own main joint leaves his root by up to 3 m in walk/run blends (drawn centred).
  A test tap of X is a ~24-frame hop: a double jump needs the second press ~12 frames after the first.
- Event 1000's PID property is a decimal UInt32: parsing it as hex never matches the crash to its gk.
- `-f` and `{0:N1}` follow the current culture (Italian: `1,18%`): set the thread culture to invariant
  in report scripts. Screenshot regressions: keep downscaled shots per version, compare at 64x36 (mean
  luma diff + SSIM over 8x8 windows) and WARN, never FAIL (weather, time and NPCs move).
- **Verifying a gate (lesson):** (1) negative check: copy the script outside the repo, break one range
  (`hour reached` 22-24 -> 30-31), run `-Only <row>`: must print FAIL with the value and exit 1; (2) headless
  really windowless: `EnumWindows` + `GetWindowThreadProcessId` per gk PID (headless: 0 windows, ~236 MB;
  windowed: 7, 1 visible, ~2.8 GB); (3) baseline: a fake baseline.json pointing a row at another scene's
  shot must WARN. Measure the metric offline first (load the gate's C# with the class renamed): at 64x36,
  a 20 %-of-frame magenta box gave sim 0.76-0.79 / diff 7-9, a different camera in the same desert 0.50,
  another level 0.15; an unchanged build rerun 0.88-1.00 (minimap present or not at 14 s, ground decals,
  pose). So MinSim 0.5 misses big partial changes and 0.92 false-WARNs on identical builds: pick per-row
  limits from several reruns, not one.
- **Fix that worked (gate v3):** the baseline keeps up to 4 rerun samples per shot (each `-MakeBaseline`
  run adds one); compare a new shot with every sample and keep the best match (a minimap shown in one
  rerun only stops mattering); per-shot limits from the samples' own spread (each sample's best match
  among the others, the worst of those, less a margin that shrinks with samples: sim 0.04+0.06/(n-1), diff
  2+2/(n-1); worked out at compare time so old baselines follow rule changes), carried over to a one-sample
  baseline from the one it was compared against; row fallback 0.85 / 6. A flat 0.05 margin on 2 samples
  left player-jak at 0.92 against 0.91: too tight. Result: 2 reruns -> boot-desert limits sim 0.88 / diff
  4.9, magenta box 0.80 / 7.8 WARNs, player rows 0.98-0.99 PASS. Reruns' diffs are small (0.2-5.8) while a
  20 % box is 7-9. Measure the old run folders offline first: they already hold reruns (a cutscene shot
  bimodal 0.63-0.99; after a level change Jak/camera stop elsewhere, 0.59): such rows need wide fallbacks.
- Check what a release script hands its gate: Jak Enhanced's release.ps1 builds `Release-static` and sets
  `JAK_RELEASE_BIN`, but the gate copied `out\build\Release\bin` (the dev build) - it tested the wrong exe.
  Pass the bin as an explicit argument (`-Bin`) and print the exe's path and time in the gate's first line;
  a release that never passes `-MakeBaseline` keeps comparing with a stale dev baseline forever.
- PowerShell variables are case-insensitive: a local `$bin` overwrote the `$Bin` parameter. And
  `Set-Content -Encoding utf8` (PS 5.1) writes a BOM, which lands in a `git commit -F` message's subject.
- Don't `tail -f` (Git Bash) a log a PowerShell job writes with Add-Content: the tail's handle makes every
  write fail silently. Read the file in polls, or watch the job's own output dir.

## Readable game and compiler logs (lesson, Jak Enhanced)

- Measure first: group log lines by a key with digits/hex replaced (`\d+` -> N), count per minute, and
  grep every regex the test scripts expect (gate rows, dev_test `ready`/`expect`, crash collector) before
  touching a line. Measure before/after on the same gate rows (boot-desert, boot-spargus,
  spargus-to-desert): the baseline gk can be a copy of `bin` passed as `-GkPath`; revert the GOAL diff
  with `git apply -R` + `(mi)` (~40 s) for the baseline, re-apply after.
- Biggest win: stock `game/main.cpp` writes `lg::debug` to the file even without `-v` (~500 "link and exec"
  lines per boot). File level info: Jak 3 desert boot 111 KB / 1400 lines -> 22 KB / 320.
- Harmless repeats: once per name (duplicate texture names, were 77 `[error]` per boot and drowned the real
  ones) or "1st, then powers of two with the count" (texture pool, GOAL warnings: `(zero? (logand n (+ n -1)))`);
  per-texture lines -> one line per page, flushed when the next page starts and when a level's upload is done.
  Never rename lines a script expects; summaries must avoid the crash collector's words (fatal, abort, exception).
- Test-mode lines printed every N frames: print on change of the values instead (gun test 54 -> 8 lines).
- goalc: progress lines to the console only (launchers parse `[ NN%]` from stdout), strip ANSI in the file
  sink, and mute the file during the REPL marker form (`(seval (error "DEVMARK-..."))`): 229 KB -> 1.3 KB per
  `(mi)`. A wrapper that logs goalc's stdout needs its own line filter (fixed-width progress entries run
  together once `\r` is dropped: `\[\s*\d{1,3}%\] \[.{8}\] (?: {6}|\d+\.\d{3} ).{0,70}`).
- The gate picks the next instance number per row: with an instance range rule (13-15), run 3 rows per call.
- Verifying a cleanup: grepping the scripts' regexes is not enough, run each one on a **baseline** log and
  look at *which* line it matched. `dev_launch.ps1 -Headless -Wait` waits for `\[enhanced\]|target`, which in
  a headless boot only matched the debug `[link and exec] target-util` lines: with the file at info it waits
  its whole BootTimeout. Also check what debug->info hides besides spam (stock `runtime.cpp` "Failed to
  initialize main memory!" is `lg::debug`; the last `[link and exec]` named the object a boot crashed in).
- Forcing real errors without touching the repo: a missing level = rename a worktree `out\jak3\fr3\<lvl>.fr3`
  for one windowed run (desinter at desert-start: `[die] Assertion ... cannot be opened`), restore in
  `finally`; a bad continue point = `JAK_ENHANCED_MENU=2:<cp>` windowed (`continue request "x": "no such
  continue point"`). A bad `JAK_ENHANCED_START` logs nothing even in stock (Jak falls from 0,0), and a
  headless gk ignores the menu request.
- Jak Enhanced `JAK_ENHANCED_TP=x,y,z,yaw` (meters, degrees) to frame a spot no continue point shows:
  yaw 180 faces +z, 0 faces -z; read the `[camera] x y z fwd ...` log line of a plain run first for
  coordinates, and put y at the floor's height (too far off it and Jak lands in the water below).
- Jak Enhanced wet-surface tests (puddles, wet stone): `JAK_ENHANCED_WEATHER_SCRIPT=0:5` (after the
  rain from the start) gives puddles in ctyport and Spargus at once. Before an A/B run that relies on a
  changed C++ default, grep that the edit landed: PowerShell `.Replace()` on a CRLF source no-ops
  silently, and the "default" variant then runs the old value.
- Without debug in the file, keep the context of a stop: a small ring of the last debug lines the file
  skipped (16), written after `[die]` (asserts go through `lg::die`) and from a Windows
  `SetUnhandledExceptionFilter` that also flushes the file (info lines are buffered: flush level warn).
  Forced missing level showed the last DVD/texture lines right after the assert.
- **Worktree GOAL builds**: `dev_goalc.ps1 -Repo <worktree>` still compiles the *main* tree (it passes
  `--proj $main`), so it rewrites the main tree's `out\` from the main sources. For a worktree run
  `goalc.exe --user-auto --game jak3 --proj-path <wt> --cmd "(mi)"` with `JAK_ENHANCED_INSTANCE` set
  (~45 s); without `--user-auto` the text step fails (`$DECOMP` must be `jak3_pal`, from the user's
  `user.gp`: "Cannot read ...\jak3\assets\game_text.txt").
- **Worktree runs that test a goalc/C++ text change** (e.g. font_utils.cpp): `dev_bin.ps1` copies the *main*
  tree's bin unless given `-From <wt>\out\build\Release\bin`, so dev_launch/dev_goalc copies with `--proj <wt>`
  still run main's gk/goalc and the texts come out with the old code. Pass `-From`, delete the worktree's
  `out\jak3\iso\*.TXT` (copies) so (mi) recompiles them, and check the bytes in `0COMMON.TXT`. Copy `out\jak3\iso`
  and `obj` (don't junction them: (mi) writes there). A test overlay loads with `(asm-file "<abs path>" :color :load)`
  (without `:color` nothing loads); capture a minimized test window with `scripts/enhanced/capture_window.ps1
  -ProcessId` (PrintWindow), never CopyFromScreen (it grabs whatever covers the window). Parallel clang builds
  beside other agents crash ("frontend command failed due to signal"): `-Jobs 4`.

## Glitch hunts from boot shots (lesson, Jak 3 Enhanced)
- A shot 3-7 s after the first `[camera]` line can still be loading: Spargus (wascityb-start) shows a
  black frame, then an orange veil with floating black palm fronds, and is normal from ~10 s. Shoot at
  10 s+ (or twice, 5 and 15 s) before calling something a glitch; report the load-in itself separately.
- The gk log is open for writing: read it with `[IO.File]::Open(path,'Open','Read','ReadWrite')`,
  `ReadAllText` throws "in use". One boot per (spot, hour, JAK_ENHANCED=0/1) at ~25-45 s each is a
  cheap sweep without goalc; tile the shots into 2x2 sheets (960 px) to keep image tokens low.

## Timed test runs: buffered logs and two script clocks (lesson, Jak Enhanced, Nov 2026)

- gk's info lines are **buffered**: a driver that screenshots "N s after it reads line X" fires late,
  sometimes after the next step already happened (two "different" presets gave the same picture). Time
  each shot from the line's own `[mm:ss]` stamp (+5 s), and space steps >= 8 s.
- `JAK_ENHANCED_MENU_SCRIPT` counts from the first frame; a renderer-side script started at the first
  composite starts ~20 s later (desert-start boot). Offset the renderer script, check in the log.
- A worktree whose change is C++/shader only needs no goalc: junction the main tree's `out\jak3\{iso,
  fr3,fr3-vanilla,obj}`, `out\enhanced`, `iso_data\jak3_pal` + `iso_data\jak3\<CGO..VAG>`,
  `decompiler_out\jak3_pal`, `custom_assets\jak3\<texture_*,merc_replacements>`, configure CMake
  (Ninja, VS clang) in `out\build\Release` (~6 min first gk build), run gk from a copied bin with
  `--proj-path <worktree>`. Never run (mi) there: the junctions would write into the main tree.
- Fix weather for A/B shots (`JAK_ENHANCED_WEATHER_SCRIPT=0:0`): snow/clouds moved luma by ~5%.
- **One long scripted run covers several items**: a `JAK_ENHANCED_MENU_SCRIPT` of blocks (pin an hour every 15 s
  for ~2 min, then `2:<continue point>`, then the next block) let one boot test Spargus 18h/12h, the arena
  12h/19h, the forest 18h and the slums 21h with tuning-file toggles in each block; wait on the log's
  `menu script <t> s` line from a small poll script (a bare leading `Start-Sleep` is blocked by the harness).
  The script's clock starts late (first frame): read the step times from the log, not wall time.
- Splitting one file's hunks over several commits without `git add -p`: a script that applies the chosen
  hunks of `git diff -U0` to `git show HEAD:<file>` (LF, as the index holds it), `git hash-object -w` +
  `update-index --cacheinfo`. `dev_build.ps1` runs clang-format, so edited lines may come back reflowed.

- Before chasing an Enhanced artifact, boot the same spot and hour with `JAK_ENHANCED=0` and count it with the same pixel mask (~2 min): Spargus palace's lime-yellow streaks at 18h showed in 7/15 stock frames too, after an hour of hot-reload bisection (glow quads painted, sprite3 painted, fx gain/knee). For bisection in a hot-reloaded game shader (`JAK_ENHANCED_SHADER_RELOAD=all`), keep every uniform referenced (`mix(c, debug, 0.999)`, `max(tex.a, 1.0)`) or the reload is refused with "uniform X moved".
- Jak 3 window panes by texture name (gfx-polish r14): only `*-litwindow*` / `*window-panes*` are named so (2-3 per city level, already lit by the game); Haven's dark windows and the far skyline's are painted inside wall textures (`city-lowres-mhcity-wall-*`, `ctyslumc-wall-LOW`): night lit-window work needs a per-texel window mask, not a name list. `JAK_ENHANCED_MATERIAL_NAMES=1` logs every texture's class. Hour drift: a menu-script hour (`2:1:18`) keeps running; ~5 min of A/B later the forest was full night and a colour-keyed mask (green lawn) found nothing. Re-send the hour before each variant or keep A/B inside ~2 min.
- Actor positions of a level without touching the main tree (gfx-polish r16): copy `decompiler.exe` + its DLLs to a scratch dir with a `data\` subdir (FileUtil then uses `<exe dir>\data` as the project dir, so fr3 goes to scratch, not the junctioned `out\jak3`), junction `data\decompiler` to the tree's, run `decompiler.exe <cfg> <tree>\iso_data <scratch>\out --version ntsc_v1 --config-override '{"game_name":"jak3_pal","decompile_code":false,"levels_extract":true,"levels_to_extract":["CTA.DGO"],"dgo_names":["CGO/GAME.CGO","DGO/CTA.DGO"]}'` (2 s): `<level>-actors.json` has etype, trans (m) and lump `name`/`art-name` (part-spawner group). Slums barrel fires (`group-ctysluma-barrel-fire`) sit at y 10.1 m, e.g. 1108.9,10.1,210.8; with the test save none drew at 21h (task-gated). Jak 3 `JAK_ENHANCED_TP=x,y,z,yaw` (m) moves Jak, yaw does not turn the camera; menu-script kind `4:0` stops the clock (time ratio 0): no hour drift during A/B.
- Spargus sea from the water (gfx-polish water review): `JAK_ENHANCED_START=wascityb-start` + menu script
  `4:1:18,12:4:0,20:3:1722.4/40/-420.1` (hour, clock stopped, teleport): Jak swims, camera ~3 m over the sea,
  rocks, an island and the horizon in view. The Hellcat test lands too early to see this sea.
- A seam at the game's near-ocean edge: profile each water term separately (final, reflection only, body
  only, fresnel channel, depth-source mask) as full-width row means over 2-3 frames, not one 90 px
  strip of one frame. Jak's swim drift and the sky reflection's streaks made a "4-row dark line" that
  a strip showed and a full-width mean did not; the real step was the fresnel (0.70 -> 0.47 over the
  10 rows where the near mesh starts) with the reflection flat. Not the pond rule, not water_deep, and
  only partly the ripple footprint (fwidth on the wavy mesh; an analytic footprint gave +5-15%).
- The composite's hot reload now takes 17-20 s (log `enh_composite reloaded (17351 ms)`): a fixed 14 s wait shot
  the old shader. Poll the log for one more `enh_composite reloaded` line before the A/B.
- Debug views in a graded composite: read one value per view in grey (`vec3(x)`), never as one channel of a
  colored view. Spargus 18h "fresnel step 0.70 -> 0.47" was the grade bending dbg 9's blue under a red flag
  (deep vs near cells); in grey the fresnel ran smooth. Haven port 18h pale sky patches in the near water: the
  Hi-Z reflection trace missed where the old 32-step march (calm mirror ray) hit (`tune_hiz_dbg 1` = old march
  on the left half); running the march only on Hi-Z misses cut pale pixels 1.3-1.9% -> 0.2-0.3% for +0.2 ms.
  A menu-script hour step logged `in none` (before the level loads) is ignored: boot with `JAK_ENHANCED_HOUR`.

## A new character on Jak's own skeleton (lesson, Jak 3 Enhanced "Wanderer", Nov 2026)

- Cheapest playable character: no skin process, no art group. Skin the new mesh to Jak's joints, build it
  as a custom model in its own custom level fr3, and in `Merc2::handle_pc_model` swap the model looked up
  for `jakb-c-lod*` with it. Every move, gun and vehicle works unchanged; hide Daxter (`(-> *target*
  sidekick)` in the draw function) and Jak's cloth (`hide!` on `(-> *target* draw cloth-instances)`).
- Force all effects on for the swapped model: Jak's GOAL enable mask can have effect 0 off, and a custom
  model is a single effect -> invisible character with a visible shadow.
- Bind pose = the rip glb's inverse bind matrices (Blender's imported rest pose is not it). Write
  JOINTS_0 in the rip's skin order (merc mat = joint index + 1) and keep `inverseBindMatrices` (tinygltf
  rejects a skin without them).
- Game joint scale is NOT inherited (the punch keys 2.5 on the hand and on each finger): an offline pose
  checker must apply each joint's scale to itself only, or the punch explodes.
- `build-level3` for a model-only level still needs a non-flat collision mesh (a box; a flat tiny triangle
  gives "bad allocation"), at least one actor and one region tree, and an existing `out/<game>/fr3` dir.
- Testing from a worktree: `dev_bin.ps1 -Repo <wt>` still copies the MAIN tree's bin unless `-From
  <wt>\out\build\Release\bin` is given (C++ changes silently missing); `dev_goalc.ps1` compiles the main
  tree. Run gk/goalc with `--proj-path <worktree>` yourself.

## Animation smoothness, foot IK and 989snd mixing (lesson, Jak 3 Enhanced, Nov 2026)

- OpenGOAL runs game logic and skeletons every rendered frame at any frame rate: there is no "PS2-rate"
  stepping to interpolate away. What looks stepped is the key blend: `process-request!` (joint.gc, the GOAL
  decompressor) goes key to key in straight lines. Measure before fixing: a REPL process that logs a joint's
  per-frame distance relative to the root (`(-> *target* node-list data 21 bone transform trans)`) showed
  speed plateaus of 8 frames (16 at 120 fps). Catmull-Rom there (4 `decomp-frame` calls, middle keys first so
  the quaternion flip test aligns the outer ones) gives continuous speed.
- Jak already has leg IK (`target-update-ik`, `leg-ik`, ground probe per foot, foot tilt). What it lacks is a
  pelvis drop; drop the drawn body through `control cspace-offset` and take it back before
  `integrate-and-collide!` (it seeks cspace-offset), or it builds up / gets eaten.
- 989snd: per-voice effects go in `Voice::Run`, the pan in degrees is in `VoiceManager::MakeVolume`
  (0 ahead, 90 right, 180 behind); a reverb send can be summed in `Synth::Tick` and mixed in `Player::Tick`.
  Group 1 is the music. The game's own `sound-set-reverb` RPC is unimplemented in the overlord.
- Test runs on a worktree need: `out\jak3\{fr3,fr3-vanilla,iso}` and `out\enhanced` junctions, `iso_data\jak3\*`
  and `decompiler_out` junctions (the custom level reads iso_data/jak3), `goal_src\user` copied; gk
  `--proj-path <worktree>`. A boot that dies with "bad allocation in loader_thread" is out of commit memory.
