---
name: retro-renderer-modern-post
description: Adding modern rendering effects to an old-console game's PC renderer (OpenGOAL Jak 3 here, OpenGL) without touching its assets - one post pass between the 3D buckets and the HUD, view-space positions rebuilt from the game's own projection, then TAA by wrapping the world shaders' main() with a per-frame jitter, volumetric mist marched in view space, sun shadow maps from the loader's world-space buffers, dynamic lights from the levels' own lamp data, screen-space sun shadows, SSAO/SSGI, bloom, god rays, water reflections; plus how to test sun-dependent effects and what screen space cannot do. Use when the user wants "next-gen" or remaster-style graphics in a decompiled/ported game's renderer, or asks for TAA, volumetrics, AO or similar in such a renderer.
---

# Modern post effects in a retro game's renderer

From Jak 3 Enhanced (an OpenGOAL fork). The game's levels have no normals (light is baked into
vertex colours) and no motion vectors; everything below works from the depth buffer and the
camera the game hands over each frame.

## The frame

- Run the effects **once, on the finished 3D scene, before the HUD buckets** (minimap, text stay
  sharp and ungraded). Copy the scene and the depth into textures first (a blit also resolves MSAA).
- **Save the game's projection where the renderer builds its camera matrix** (here
  `make_new_cam_mat`): depth constants, fx, fy, the world->view rotation and the camera position.
  With them: view position from depth, world position, world up in view space (fog by height),
  the previous frame's view (reprojection), the sun in view space.
- Check the scale factors the vertex shaders apply (here y is scaled by 512/416 * 0.5): the
  rebuilt positions are wrong by exactly that factor otherwise.
- Every effect is a setting with an ImGui slider and an env switch (`JAK_ENHANCED_<X>`), so test
  runs can turn one off without rebuilding.

## TAA in a renderer that has no velocity buffer

- **Jitter**: wrap the vertex shader source at load time - rename `void main()` to
  `enh_original_main()` and append a `main()` that calls it and adds `enh_jitter * gl_Position.w`
  to `gl_Position.xy`. Only for the shaders that draw the world into the frame (level, actors,
  particles, water, sky); never the HUD, post passes or anything drawing into offscreen textures
  (texture animation, eyes, sky blend). Set the uniform once per frame for every program
  (Halton 2,3, 8 samples, in NDC: pixels * 2 / size).
- **Resolve**: reproject with the camera only (depth for the world, rotation only for the sky),
  Catmull-Rom history fetch (stays sharp), variance clipping in YCoCg against the 3x3
  neighbourhood (this is what stops trails on characters that move with the camera), less history
  on fast pixels, reset on a camera cut. Ping-pong two RGBA16F buffers.
- Composite then reads the TAA output; switch FXAA off while TAA runs.
- Cost here: ~0.1 ms. Compare a still shot with it on/off, zoomed on thin diagonals.

## Volumetric mist

- Half resolution, march the view ray to the depth (24 steps, jittered per pixel and frame - the
  TAA smooths the noise), density = ground mist falling with height above the camera, patches of
  drifting 3D noise in world space; light = fog colour + sun * Henyey-Greenstein phase * sun
  visibility. Upsample with depth weights or the mist behind a character bleeds over it.
- **Sun visibility in screen space** (march toward the sun through the depth buffer) only gives
  soft darkening; crisp shafts in alleys need a real sun shadow map (below). Keep the visibility
  test in one function so the shadow map can replace it.
- **Energy**: forward scattering toward the sun blows out quickly; cap the sun term and start
  subtle (density ~0.004/m, falloff ~4 m). Water and low ground far below the camera are inside the
  densest layer - judge the defaults on a view over water.

## Sun shadow map from the loader's data

- No need to touch each renderer: the loader already holds the static level geometry on the GPU
  with **world-space vertex positions** (tfrag and non-wind tie are pre-transformed; here
  `LevelData::tfrag_vertex_data`, `tie_data`, stride = `PreloadedVertex`). Draw it depth-only from
  the sun with one tiny shader and one VAO rebound per buffer. Tfrag keeps its indices on the CPU
  (streamed after culling) - upload them once per level load id, free them when the level goes.
  Skip LOD/low-res and water trees, honour strips + primitive restart.
- Orthographic map around a point ahead of the camera, **snapped to whole texels** in light space
  (no crawling edges), 4096 over ~160 m; depth 32F with hardware compare (`sampler2DShadow`),
  polygon offset, normal offset at lookup, fade at the edge. Save and restore the game's depth
  clear value and depth func.
- Any geometry the game's shaders discard (cut volumes) must be discarded in the shadow pass too.
- Apply it only on surfaces facing the sun (normals from depth), at ~35 %: the baked vertex light
  already darkens what faces away, and a full-strength shadow over a mostly-shaded area crushes it.
- Characters: the skinned renderer (here Merc2) uploads one bone buffer per flush and reuses it.
  Copy its bones (CPU side, at an aligned offset) and its opaque draws as it flushes, then replay
  them in the shadow pass with a depth-only copy of its vertex shader. The bones end in camera
  space: back to the world with the saved camera. **Check the sign**: here merc's camera space is
  the view space negated (`-X * p`), and the first try put every shadow behind the camera. Debug
  it by logging the bone translation nearest the player in world space - it should land within
  centimeters. Many bone slots are uninitialized garbage; only the ones vertices reference matter.
- Wind-swayed props (instanced, a matrix per instance swayed each frame): bake the still instance
  matrices into one world-space buffer per level; only the translation's xyz is a position (w holds
  other data). Alpha-test their textures in the shadow pass or leaf cards cast solid squares.
- The game may already draw its own short shadow under the player; the sun-map one just adds the
  long cast, so leave the game's on. Test casters with the strength at 1.0 and the sun turned
  sideways (`JAK_ENHANCED_SUN_YAW`), then judge at the real strength.
- The volumetric mist's sun test becomes one shadow-map lookup -> crisp shafts through gaps.

## Dynamic lights from the game's own lamps

- First try: every glow sprite (the renderer's "flare" quads) as a point light. Almost invisible:
  glows are few, faint (colours ~0.15), often doubled, mostly high up or far away (the moon is
  one) - normalise the hue, merge duplicates, cull by distance, but don't rely on them alone.
- The real source is the level data: Jak's levels carry **light spheres** (`light-hash` ->
  `light-sphere-array`: bsphere = position + radius, rgb colour, brightness, a time-of-day
  palette index whose `mood-context times[i].w` switches night lamps on). The game only uses them
  to light actors. A small GOAL function in the time-of-day update sends the ones within 80 m of
  the camera through one kernel call (array of vector pairs, copied under a mutex because the
  renderer runs on another thread). That's what lights the street at night.
- Shade them in the composite: normals rebuilt from depth (pick the smaller-difference neighbour
  on each axis), `(1 - d^2/r^2)^2` falloff, wrap lighting (`ndl*0.85+0.15`), tinted by the scene
  colour plus a small constant so dark surfaces still pick up light. Up to 32 per frame, sorted by
  brightness * r/(dist+r). Start ~0.75: a strong lamp next to a wall burns it white.
- Test at night: a switch that sets the hour after boot (`JAK_ENHANCED_HOUR`), on/off pairs
  side by side. The AO debug view hides the lights - take the shots without it.
- Shadows for them in screen space: per pixel, for the few strongest lights in range, 8 jittered
  steps toward the light through the depth buffer (up to ~3 m, stopping short of the light: lamps
  sit inside their housing), blocked when the depth is in front by less than a thickness (~1.5 m).
  Back faces only get wrap light, so a "blocked" debug view must weight by the light actually
  removed or it looks wrong everywhere. Cost ~0.05 ms.
- Runs aren't deterministic (camera, NPCs): for an A/B in one frame, apply the effect to half the
  screen (`tex_coord.x > 0.5`) temporarily.

## Fires from the glow sprites

- The glow sprites are the cheapest source of "where is a fire": an orange-to-yellow glow, flame
  sized. But colour alone also catches muzzle flashes and shots (a firefight lit the whole test
  scene). Keep a small memory of warm glows by world position (merge within ~1.5 m: a flame is
  several glows that come and go): a fire is one that has glowed there for a second in most frames
  (~60%+); a gun fired from a standing enemy glows in bursts, shots move on.
- Texture names don't help (fires and lamps share the generic glow texture).
- With the fire positions: flicker their light, wobble the scene's uv in a column above each flame
  (only for pixels behind it), and draw procedural embers in the composite (hash per ember and per
  life cycle, rise + sway, depth-tested against the scene, a screen-rect early-out per fire).
- To find a test spot, log the glows with their position, then drop a debug dot at the projected
  fire position to check the projection before tuning anything.

## Testing light-dependent effects

- The key light the game hands over is not the sun disc in the sky texture; log its view-space
  direction before judging shafts or shadows.
- Add a test switch that **turns the sun around the up axis** (`JAK_ENHANCED_SUN_YAW`), not one
  that negates it (that puts it under the horizon and every sun effect switches off). Log the
  view-space sun for a few yaws, pick the one in front of the review camera.
- Exaggerate first (10x density, 3-5x sun) to see the structure, then tune down.
- Continue points rarely frame what you need (water from close by, a shallow beach). A test switch
  that **teleports the player** shortly after boot (`JAK_ENHANCED_TP=x,y,z,yaw` in meters) takes
  any spot from the logged camera positions; plus an off switch per feature for A/B pairs.
- Test boots log the loaded levels and a census of live actors by type name: it settles "are there
  enemies / is this bank loaded" questions in seconds instead of guessing from screenshots.

## Water in post

- The sea's own renderers write no usable surface: keep its depth (copy right after the far-sea
  bucket; make the near sea write its surface, then restore the depth) and shade it in the
  composite: noise ripples faded by pixel footprint, a long swell in the normals only (calm it in
  shallow water and at distance or it shimmers), Fresnel, screen-space reflections.
- Shallow water: depth below the surface from the sea-bed depth; refract the sea-bed sample by
  the slope, but only where the bent sample is still under water, or things standing out of the
  water smear into it. Caustics = two drifting ridged-noise layers multiplied, scaled by the sun
  and faded with depth.
- Effects lying on the water (splash and ripple discs) write depth a few cm above the sea, so a
  naive "scene in front of the sea = not water" test shows the game's darker water there as a
  disc. Treat a pixel as water when the scene is just above the sea surface, and composite with
  `max(ours, game)` there so the foam still shows. Only trust a sea depth that is really behind the
  scene (a plane under the whole level, or a depth copy where something hid the sea, matches the
  scene itself: docks turned into water and lost their shadows). Check with an A/B of a dry scene.

## Real normals for levels that have none

- Compute them **at load, not at extraction**: the loader already unpacks the level's vertices
  (here `TfragTree/TieTree/ShrubTree::unpack`), so no re-extraction and no file format change.
  Weld vertices by quantized position across strips, average area-weighted face normals that lie
  within ~60 degrees of the vertex's own faces. Winding isn't consistent in these meshes: compare
  with |dot| and align signs, flip toward the camera in the post pass. Keep the game's own normals
  where it has them (envmapped ties). Spare words in the vertex struct hold them (10:10:10).
- Strip vertices sit on both sides of hard edges, so some smooth normals still round a corner off
  (big lit triangles on flat walls). Fix in the fragment shader: the face normal from
  `cross(dFdx(pos), dFdy(pos))` (pos relative to the camera, for precision), keep the smooth one
  only within ~35 degrees of it.
- Write them to a **second color attachment** of the game's framebuffer (RGB10_A2, a = 1 written,
  cleared to 0 each frame), but only while the level renderers draw (`glDrawBuffers(2)` in a scope
  that checks the bound framebuffer) and only for opaque, depth-writing draws (`glColorMaski(1,
  ...)` in the shared draw-mode setup). Every shader that can run in that scope must declare
  location 1 (write 0 where there's no normal, e.g. wind or envmap passes).
- Post: one `surface_normal()` that uses the stored normal where a = 1 and the depth-rebuilt one
  elsewhere (characters, water). A split debug view (stored vs depth-rebuilt, same colors) proves
  the space conversion in one shot.
- A/B shots at night can differ because the lamps arrive a few frames late: retake before blaming
  the change.
- The normal target only gets what's drawn while it's on: characters drawn later keep the level's
  normal behind them unless their renderer writes one too. Skinned-mesh normals may be in view
  space even when the lighting code reads like world space: test both spaces against the face
  normal from derivatives (color the pixels where each agrees within ~35 degrees) - one wins
  everywhere. Write the smooth normal where it agrees with the face, else the face's.
- Once the stored normals exist, feed them to SSAO/SSGI too (same texture, same conversion).

## Grass that reacts to the player

- Vertex shader only: the game sends the player's position each frame (one kernel call), cutout
  vegetation draws lean away within ~1.3 m and press down, scaled by tip^2 (texture v as height:
  feet stay planted), on top of the wind sway. Test it with a huge radius (25 m) from the spawn
  point and a difference image: the effect is too local to see at the real radius in one still.

## Denser vegetation without new assets

- At level load, after the loader unpacks the shrubs: group strips into plants (welded by
  position), keep the small ones made of crossed cards standing on the floor (floor = the level's
  upward triangles on a 2D grid). Copy each a few times nearby, turned and scaled, only where the
  floor continues halfway (no copies over ledges or through walls).
- Fuller patches: tufts of a nearby plant's **own upright cards** (tall and slim, so pebbles and
  litter never become brushes), only on floor textures that already carry 3+ plants and fading out
  within ~4.5 m of one - the desert stays bare. Count candidates first, then thin evenly to a
  budget; capping as you go spends it all on the first floors in the file.
- Extra draws carry a tier (moderate / lush) and the renderer skips tiers above the setting, so the
  menu switches density live. Judge it on A/B stills of the same spot.
- Climbing plants: don't lay grass cards flat on walls (they read as spiky grass). Look for the
  game's **own** wall vines first (shrub textures named `*vine*`, flat on a wall) and copy those
  onto nearby walls, turned so their facing matches the new wall and kept as high above the floor.
  A wall is many small triangles: chain the coplanar ones above and below the spot to get its real
  height, or every tall vine gets rejected. One vine per small cell, so copies don't pile up.
- To find where a loader-placed effect landed, log a few positions, then teleport *several meters
  out* facing it. Teleporting next to it puts the camera inside the bush or the wall.

## An in-game menu for the player

- Once there are many effects, give the player one ImGui window on a free key (here `\`): the
  effect switches, the time of day, quick travel. Register the key as an input command (those fire
  on the SDL event even while ImGui has focus), draw the window after the debug windows.
- The renderer thread can't call game code: the menu queues **one request** (kind + string under
  a mutex), the game polls it each frame through one kernel call and acts in its own code
  (time-of-day event, continue point, teleport).
- Free the cursor while it's open (a mouse camera keeps it in relative mode) and leave out the
  window's close button, so the key is the only way out and always restores the mouse.
- A test switch that opens it at boot and queues one request lets a scripted run check every
  path with a screenshot.

## What screen space can't do

Off-screen occluders, light from behind the camera, anything hidden behind the foreground. The
next real steps are geometry-side: normals computed at extraction (better dynamic lights), shadows
for the point lights, then ray tracing (compute-shader BVH, or Vulkan).

## Menu presets and saved choices

- Keep the in-game menu's choices in one JSON next to the port's own settings (OpenGOAL:
  `file_util::get_user_settings_dir(g_game_version) / "enhanced-settings.json"`). Load it in the
  renderer's constructor *before* the env test switches, so test runs stay reproducible; write it from
  the menu by comparing the dumped JSON with the last one written (no per-widget "changed" plumbing).
- Values the *game* owns (e.g. population read by GOAL at boot) must be re-sent at start through the
  same request queue the menu uses, or the saved choice shows in the menu but not in the world.
- Presets = three buttons that set the fields, not a separate mode: Classic (pass off), Medium
  (drop the passes that cost the most: volumetrics, SSGI, DOF, god rays, light shadows, refraction),
  Max (struct defaults, taken from a default-constructed `Settings`).
- Test configs (`--config-path`) get their own settings file: delete it after a load/save test.
- Writing C++ through a shell heredoc + Python: `"\0"` can reach the file as a raw NUL byte (grep then
  calls the file "binary", ImGui combo strings still compile). Write such bytes with `bytes([92, 48])`
  and scan edited sources for `\x00`.

## Footprints, ruts and other "pressed in" decals in post

- Let the game say *where* (the player's ground collision material: sand/dirt/snow) and keep the
  shader test loose (flat, not green): retro sand is often neutral white after the game's lighting, so
  a "warm color" test rejects it.
- Bright ground is over 1.0 before tonemapping: multiplying it by 0.7 still clips to white. Clamp it to
  1 inside the decal (`mix(c, min(c, 1), mask)`) before darkening.
- Debug decals by painting a flat color where each test passes (`c = vec3(sandy, level, rim)`), not by
  adding to the color (invisible on clipped white).
- Synthetic test data must land where the camera sees it: a row "straight ahead past the player"
  hides behind the player's body from a chase camera. Lay it beside the player, re-seed every few
  seconds (a seed at the first valid frame lands where the player was during loading).
- Injected key events (`keybd_event`) did not reach the OpenGOAL window in test runs: prefer a test
  switch that fakes the state over driving the player.

## Lighting the particles (smoke, dust, steam)

- Hand the post pass's strongest lights (already sorted, view space) back to world space for the
  next frame's particle draws; light the *normally blended* particles only (additive ones are
  light already), per vertex, multiplicatively (`rgb *= 1 + light`) so the particle keeps its own hue.
- Check a per-draw effect with a counter of draws by blend mode and of draws that took the path,
  before guessing at the shader: here the path was fine and the strength was 0 because an A/B run
  had saved its test switch into the settings file.
- Saved settings: take what's in effect after loading the file *and* the env switches as the
  "already saved" baseline, so a test run never writes its switches to the player's file.

## Software ray-traced reflections on an OpenGL 4.3 renderer (lesson)

- No hardware RT in OpenGL, but SSBOs are there: build a BVH per level on the loader thread (binned
  SAH, 4 triangles a leaf, depth-first so the left child is the next node; a 160k-triangle PS2 level
  takes ~0.06 s), upload each once, copy the levels in use into one buffer set with
  glCopyBufferSubData when the set changes, pass per-level bases as uniforms.
- Trace only where the screen-space reflection misses: same picture where SSR works, real geometry
  where it fails (off-screen, occluded). At 60 fps the cost didn't show.
- Shade hits like the game would: keep per triangle the texture's mean color and the vertex's
  baked time-of-day color index, and weight the 8 palettes with the frame's itimes (64 = 1), so
  night reflections are dark.
- A debug mode that paints only the traced color (misses in magenta) proves it works; mixed into
  the normal image the difference is easy to miss.
- Mean colors per triangle look flat and blocky ("non funziona bene"): users notice at once. Keep
  a small texture per material (64x64 layers of a GL_TEXTURE_2D_ARRAY, mipmapped, REPEAT) plus
  per-triangle UVs (80-byte triangles = 5 vec4), interpolate with the hit's barycentrics and pick
  the mip from the hit distance. Combine the per-level arrays with glCopyImageSubData.
- Never switch traced/untraced reflections at a hard distance on water: it draws a horizon line.
  Fade the traced contribution over a band (150-200 m).
- Ray-traced AO falls out of the same BVH: 6 cosine-weighted 3 m rays per pixel in the SSAO pass
  (nearest-hit traversal, linear distance weight). Take min(traced, SSAO): characters aren't in
  the BVH and keep their screen-space contact shadows. In open squares it barely shows; check in
  a debug view that outputs the traced term alone (window recesses darken) before tuning.
- Call the BVH update once per frame before the first pass that uses it (here SSAO), not inside
  the composite.

## Area looks, weather, soft shadows and cutscene DoF in post (lesson)

- **Tell the renderer where the player is.** One kernel call per frame from the game's time-of-day
  update (level name of the level the player is "inside", the hour as a float, whether a cutscene
  runs) unlocks a lot: a color grade per area and per day/night, weather by area, cutscene-only
  effects. Ease every target (grade ~1.5 s, weather ~4 s) so level changes and nightfall don't snap.
  Gate sky/weather effects on "is there a 3D scene this frame", or they paint over loading screens.
- **Grade per area** as lift (added in the shadows: `c*gain + lift*(1-c)`), gain, saturation,
  contrast and warmth on top of the global settings; a small table of day/night looks per area is
  enough. Classify areas by level-name prefix.
- **Rain that sells it at night** is mostly the wet ground, not the streaks: darken level ground,
  reflect the screen with the existing SSR march (windows and signs on the street), more in puddles
  from a world-space noise and at grazing angles, plus the dynamic lights' Blinn glints on wet
  surfaces. Streaks: a few layers on a grid of the view ray's world azimuth/elevation (they turn with
  the camera), each layer hidden behind nearer depth; derive line width from `fwidth` computed in
  uniform control flow, before any per-layer `continue`. Raindrop rings: keep them sparse (skip
  cells per cycle by hash) or they read as bubbles.
- **Soft shadows (PCSS) with a hardware-compare shadow map**: bind the same depth texture to a
  second unit through a *sampler object* with `GL_TEXTURE_COMPARE_MODE = GL_NONE` for the blocker
  search; unbind the sampler after the draw. Penumbra = blocker gap x ~0.02; grow the bias with the
  filter radius; rotate the Vogel disk per pixel and frame and let TAA average it.
- **Cutscene autofocus without a stall**: `glReadPixels` a few depth texels around the screen center
  into two alternating pixel-pack buffers, map last frame's, ease the focus in log space. Gather DoF
  with per-sample CoC: a sample counts where its blur reaches the pixel; a farther sample only up to
  the pixel's own CoC (no sharp-subject bleed).
- **Clouds without a volume march**: one noise sheet at a fixed altitude along the view ray
  (flattened toward the horizon), lit by sampling the sheet again offset toward the sun.
- **Window capture in test runs**: `PrintWindow` gets a 0x0 client rect when the game window is
  minimized; restore it with `ShowWindow(h, SW_SHOWNOACTIVATE)` first.
- **Weather must live in the world, not on the screen**: any noise indexed by screen angle reads as
  "blotches stuck to the lens". Dust and fog: march a few jittered steps (quadratic spacing, more
  near) through 3D noise at *world* points, stretched along the wind and offset by an accumulated
  drift (wrap it rarely; rotating a wrapped drift breaks periodicity). Use an integer hash for 3D
  noise far from the origin (`sin` hashes band at kilometer coordinates).
- **Start from the game's own effect**: if the original has a storm (e.g. a dust-storm process with
  intensity and wind globals), have it call a kernel function each frame to hand those to the
  renderer, and time the values out when the process stops sending. The post effect then follows
  the game's own triggers and matches its particles' wind.
- **Showcase weather states**: a "changing" cycle (clouds build, rain, thunderstorm with bolts and
  flashes, sun back on wet ground with shafts, steam and a rainbow at 42/51 degrees from the
  antisolar point, slow drying) shows off wet reflections, halos and shafts far better than a
  static toggle. Keep ground wetness separate from rain (soak fast, dry over ~90 s).
- **Storms read through the sky, not just bolts**: add sheet lightning (the whole cloud layer
  flickering from inside, 2-3 pulses within ~0.4 s, every 2-6 s) on top of the bolts, and let the
  puddles spread with storm strength. A timed weather script from level entry (`<s>:<mode>,...`)
  makes videos repeatable.
- **Social cuts of gameplay** (vertical 9:16 from a 16:10 capture): crop around the player below any
  capture strip, paint out debug markers (`delogo`), skip stretches where the game's own subtitles
  would be cut by the crop. Small captions low on screen (~79% height) with soft shadows read
  better than big titles. Encode per platform: YouTube Shorts upscaled to 1440x2560 (much higher
  bitrate tier), TikTok 1080x1920 60 fps, Instagram 1080x1920 **30 fps** (~25 Mbps, H.264 High,
  BT.709, AAC 320k, faststart); on the IG phone app turn on "Upload at highest quality". Rain and
  particles are the encoder's worst case, so a light unsharp after the Lanczos scale helps.

## One post renderer for several games of the same engine family (lesson)

When one runtime runs several games (OpenGOAL: Jak 1, 2, 3), keep the effects in one shared
renderer and give each game only three thin layers:

- **A hook in the game's bucket dispatch**: post on the finished 3D scene right before the first
  sprite/HUD bucket, ocean depth captures around that game's ocean buckets. Find the HUD bucket per
  game; the enum names differ.
- **Bridges in the game's own scripts** for what only the game knows (sun direction, level, hour,
  cutscene, player position, who pushes the grass, menu requests, test boot point). Shared kernel
  functions, one call site per game. Older engines lack things (Jak 1 has no light spheres): send
  zero rather than skipping the bridge.
- **Data, not code, for everything tunable**: zones by level-name prefix per game, day/night grade
  per zone, weather per zone (fixed values, a periodic "harder" window, spells of fair/wet weather
  picked by a hashed roll per spell, morning mist), per-game scale for bounced light and lamps. One
  commented JSON, polled once a second and reloaded on save: tune while playing. Level names
  collide across games (Jak 1 and Jak 2 both have "sunken"): one prefix list per game.
- A **checker script** that greps each game for the hooks and bridges, validates the data and
  lists the levels in no zone makes porting the next feature a checklist.

Per-game tuning matters: the same GI is too bright on a game whose levels are lit brighter, and an
already saturated game (Jak 1) burns under a "sunny" grade meant for a duller one; scale it to ~0.3.

Snow in post: the rain's world-cell columns walked along the view ray (2D DDA), but round flakes
(miss distance and vertical offset as one 2D distance), ~1 m/s fall, the whole column swaying, the
wind shearing space a little. Hot air over lava: offset the sampling uv with a rising sine pattern,
stronger where the pixels a little below are lava-colored (red minus blue, bright red).

## Dark nights, light and reflections in post (lesson)

- **Dark nights**: the game's night is a uniformly dim, blue-tinted day. Darken by a zone factor
  (desert darkest, cities least) but *keep the brightest pixels* (`smoothstep(0.4, 0.85, luma)`):
  those are windows, fires, signs. Then the dynamic lights re-light the darkened image using the
  pre-darkening color as albedo (warm-corrected: the game tints night albedo blue). Add a little
  eye adaptation from a 5x4 grid of scene samples, and spare a few meters around the player.
- **Everything that reads the scene texture must be darkened too**: reflections (SSR, ray-traced,
  screen-edge env) sample the undarkened scene and glow in the dark; water's own body color isn't
  part of the scene pass either. One `night_dim(color)` applied where reflections are returned
  fixes all of them at once. Fog, mist, rain haze, GI: scale them down at night as well.
- **Light spill** from emissive pixels: the bloom texture is already "the bright pixels spread
  wide"; at night add `albedo * min(bloom, 0.5) * k` to surfaces that aren't bright themselves.
  Cap it hard: in a zone lit by one color (a red factory) the bloom is everywhere and floods it.
- **Many lamps add up without end**: soft-saturate the summed light (`added /= 1 + 0.35*max`)
  and let an over-1 colored result bleach toward white (`mix(c, vec3(max), (max-1)*0.35)`)
  before the highlight roll-off; per-channel clipping alone leaves flat pure-red walls.
- **Lamp images on water**: a Blinn highlight per light with the water's wave normal (`pow(nh,
  500)`), *not* limited by the light's radius (you see a lamp's reflection far beyond its light),
  makes the shimmering column of a harbor at night. Headlights: only from in front of the beam.
- **Cloud shadows**: march from the ground point toward the sun to 2-3 heights in the same 3D
  cloud field the sky draws (2 noise octaves is enough); patches drift with the clouds for free.
  Fade when the sky is fully overcast (all shade then).
- **Lights placed by hand**: a JSON list per game (world position in meters, radius, color,
  flicker, night-only) merged into the light candidates, plus a menu button "add a light where
  the player stands" that writes the file. A light with no visible source looks fake: place them
  at real lamps/windows, don't sprinkle them blind. Log the player's world position in the
  periodic stats line so you can place them from test runs.
- **Testing a screen-anchored effect (lens flare)**: force its anchor and multiply the output x20
  with a magenta tint in a throwaway shader edit to see that it draws and where; then hunt the
  real-world multipliers (a sun-height factor near 0 hid it). Remove the hack with a marker grep.
- Before blaming your post pass for an artifact, take the same shot with the post pass off: a
  checkerboard over a Haven district at night was the game's own.
- Patch scripts: normalize CRLF (`git stash pop` can bring a file back with CRLF and an exact-match
  assert fails); and never put a `//` comment between `if (...)` and its `{` in a sed edit.

## Puddles, embers, beam dust and presets (lesson)

- **Puddles that outlast the rain**: keep a separate `puddle_level` that rises fast (~20 s) and
  falls slowly (~220 s), apart from the surface wetness; shrink the puddle mask's threshold with it
  so puddles dry from the edges in, and only on flat ground (normal.y gate), with a darker damp rim.
- **Rain bounces** reuse the footstep splash slots: tiny strength-0 splashes spawned a few meters
  around the player at a rate tied to the rain, short life; the shader treats strength < 0.5 as
  "rain drop" (three 1 cm droplets) instead of a step splash.
- **Fires from the game's own particle spawners**: the glow-sprite detection misses fires whose
  sprites are dim; hook the part-spawner's update to report FIRE-kind spawners within ~40 m and
  merge them (one entry per 2 m) into the fire list that gets embers and heat haze. Some embers
  as rare white-hot "pops" (fast, only some cycles) make a fire feel alive.
- **Dust motes in headlight cones**: a world-space grid (one mote per 0.3 m) tested against each
  cone, with a per-cell hash that *skips* most cells; without the skip the motes line up in visible
  vertical columns. Size from distance (`max(1 cm, depth*pixel*1.2)`), stronger in sandstorm/rain.
- **Hand-placed fill lights need a `bulb` flag**: a light in a dark alley has no lamp model, and
  drawing its beacon dot shows a light floating in mid-air. Pure-hue colors read as tinted
  (a purple-ish industrial light): use warm whites.
- **A Performance preset**: start from Medium and turn off what costs GPU (shadow map, SSAO, sun
  shadows, water reflections, far view, light spill, lit smoke, cloud shadows, relief, extra
  vegetation). Renderer timers on the CPU barely move; measure on the GPU or by fps.
- **Pad access to a debug/settings menu**: a two-button combo (Select+R3) read with the pad's own
  button state; while the menu is open zero the game's axes and swallow button-downs, and turn
  ImGui gamepad navigation on only then.

## A start menu over a booting game, and testing it by keys (lesson)

- **Start menu without a second program**: draw it as a fullscreen ImGui page over the game that is
  already booting (darkened), and pick another game by the runtime's in-process switch. The game's
  own title/intro keeps running behind; the menu only has to own the pad (same flag as the
  settings menu) and the keyboard (skip the game's keyboard poll and the global shortcuts while it
  is up). Show it once per process, so a later switch goes straight into the game.
- **Launcher remembers**: the game writes "last game played" next to its settings; the launcher
  boots that one, so the most common choice (same game again) costs no restart.
- **Path helpers**: check what a "config dir" helper already appends (OpenGOAL's
  `get_user_config_dir()` already ends in `OpenGOAL`, adding it again made `OpenGOAL\OpenGOAL`);
  deriving from the settings dir (`parent.parent`) also respects a `--config-path` override.
- **Driving it from a script**: `WScript.Shell.AppActivate(pid)` + `SendKeys` works for Enter and
  letters, but `{LEFT}`/`{RIGHT}` arrive without the extended-key flag, which SDL reads as the
  keypad (KP_4/KP_6): bind A/D as well (useful anyway) and test with those.
