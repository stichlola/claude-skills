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
- Don't key the lamps' and fires' strength only on the clock (night factor): indoors (temples,
  caves, palace halls) at noon they then stay at day strength (Jak 3 temple: ~1/4 of the night's), so
  the torches light nothing on the floor. Give the light rig an "enclosed" factor too (area flag, or
  little sky visible on screen / no sun shadow coverage).
- With the fire positions: flicker their light, wobble the scene's uv in a column above each flame
  (only for pixels behind it), and draw procedural embers in the composite (hash per ember and per
  life cycle, rise + sway, depth-tested against the scene, a screen-rect early-out per fire).
- To find a test spot, log the glows with their position, then drop a debug dot at the projected
  fire position to check the projection before tuning anything.
- Many placed fires are story-state gated (spawner perm "subtask-complete", kill-mask): a spawner
  list from the level's actors is not proof a fire burns in your save. Look for a burning one from
  a wide shot first (far beacon/glow), then teleport toward it along the view ray.
- "Pale flame" is often the game's own sum of additive sprites (clipped to cream), not your grade:
  keeping the raw game pixels made it paler. Restore hue past the grade instead (saturate toward
  orange, luma held), masked by warm color inside a tall column above each reported fire.

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
- Pale band under a far quay (Jak Enhanced, Haven port 17h, 4-8 px at 640x360): first prove whether it is a  reflection *miss* with a hit/no-hit debug view (hits red, planar-mirror share green) before tuning. It missed in  both the Hi-Z trace and the old march, and none of near-reject 0.5 -> 25 m, +25 m hit thickness, the planar  mirror ray on Hi-Z, 400 iterations changed the hit count (count debug-colored pixels, 4 shots, A/B/A/B): drop  variants that move nothing instead of shipping them. Next suspect: the water point p itself (which depth  feeds it right at the waterline).
- Before calling dark vertical shapes on near water an artifact, check the hits view and the geometry: from a camera 2-3 m over a harbour (Jak swimming), the mirror of 20-30 m tall dark buildings 60-150 m off lands near the camera, close to a mirror about the horizon. The direction-only fallback (the screen where the reflected ray ends at infinity) is close to right there. Jak Enhanced water spots: `ctyslumc-start` (a pool, its edge in view), `ctygenb-start` (the camera faces the canal wall, no view of the bed), `desert-ashelin` (the oasis pond is out of view: needs a turn).
- Hour schedules in `JAK_ENHANCED_MENU_SCRIPT` run on the game clock from its first frame, not from when the launcher returns (boot 15-40 s). Give each hour a window of at least 50 s and shoot in the middle of it, or the "18h" shot shows noon.

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
- **Marking a material in the normal target**: RGB10_A2's alpha has only **2 bits** (0, 1/3, 2/3,
  1), so a marker like a = 0.92 reads back as 1. Encode it in the **normal's length** instead (sand:
  `n * 0.9`, detected with `length(rgb*2-1)` in 0.85-0.95) and have every other reader normalize.
  Tag the material by texture name at load (e.g. contains "sand" but not "stone/rock/wall/bag").
- **Procedural detail in post** (sand ripples, grain) faded by distance shows as a ring that follows
  the player. Fade each octave only by its **pixel footprint** (m per pixel = dist x pixel angle /
  |cos of the view to the surface|; visible while a wave spans ~3+ pixels) and add bigger octaves
  (0.24, 1.1, 3.6, 11 m) so a fading small one is never the edge.
  Better still (what the user accepted): measure the footprint **across the crests** with
  `fwidth(dot(world_xz, across))` computed outside any branch - crests running toward the camera stay
  sharp far beyond the isotropic worst case. Make each size a scaled copy of the smallest (wiggles
  too) and **renormalize** the octave weights so contrast stays constant as small ones drop out; then
  fade crests that run across the view with distance (they read as strong horizon stripes).
- **Don't gate post detail on the color** when a haze runs earlier in the same shader: the warm haze
  turned far sand orange, the hue test failed and the ripples "stopped" at a fixed distance.
- **Triplanar detail in post**: don't fade by texel size; read with `textureLod` at
  `log2(m_per_pixel * tex_size / tile_m)` (no implicit derivatives inside branches) and let the mips
  average it out; add a big tile (~40 m) so whole mountains get strata. Debug a material marker by
  painting marked pixels pure red first - it showed the marker was fine and the fade was the bug.

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

## Reading the per-pass GPU timers

- Wrap the whole post pass in one timestamp scope too and log it next to the passes: **total minus the
  sum of the passes is the untimed work**. In Jak 3 Enhanced (640x360, 60 fps) the total was ~10-12 ms
  while the timed passes summed to ~2-3 ms, with frame GPU ~15 ms: the gap, not any named pass, was
  the budget to hunt first (untimed draws, synchronous uploads/readbacks, or CPU gaps inside the scope,
  which GPU timestamps also count). Time every draw before tuning any single effect.

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
- Far water's SSR found nothing (Jak Enhanced, Haven harbour 120-200 m off): from a low camera the
  view grazes the water by 2-5 deg, so a ripple normal tilted ~1 deg toward the eye sends the reflected
  ray down into the sea. Past ~25-50 m march the calm plane's mirror ray (`reflect(v, up)`) instead and
  wobble the hit's uv by the ripple slope (a screen-space planar mirror); loosen the "occluder in front"
  reject there too (a quay rises only 2-5 m behind the water's edge, inside a 3%-of-depth margin).
  Debug first with a hit/distance/fresnel false-color view: it showed the harbour lay at 150-200 m,
  past the march's 80 m cutoff, before any tuning. Cost at 640x360 within noise (32 growing steps).
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
- **Adding kernel functions can break boot (OpenGOAL jak3)**: one more `make_func_symbol_func`
  made gk crash a few seconds into gameplay (access violation in GOAL code, no useful stack), with
  the game's GOAL code untouched. Bisect C++ and GOAL separately (revert GOAL to HEAD first: if it
  still crashes, it's the kernel). Instead of a new symbol, widen an existing call's buffer (a
  `(new 'static 'inline-array vector 2)` passed to the same function) and pass values in and out
  through the extra slots; guard the extra slots by game version when the C function is shared.
- **Analog L2 on PC**: the game only sees L2 as a button; read the SDL trigger axis
  (`SDL_GAMEPAD_AXIS_LEFT_TRIGGER`, 0..32767, small deadzone) in the controller code and hand it to
  the game through a kernel call, falling back to the digital button (keyboard).
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

## Holding the boot behind a menu, and HD art for streamed windows (lesson)

- **Holding the boot** (wait before the game's main until the menu closes): the IOP/overlord and the
  debugger link are already waiting for the EE. To leave without booting, release them first
  (send the overlord its stop status, kill the IOP library, disable DECI2) or shutdown hangs.
  While held, the window shows nothing: bind the default framebuffer, clear it and draw the menu
  yourself every frame; switch a windowed start to borderless on the first menu frame.
- **HD replacement of a texture the game streams in windows** (e.g. a pause map uploaded 256x416 at
  a time from a bigger image): have the game script tell the runtime which image is up (one kernel
  call with its index and address), recognise the window upload by destination and size, derive
  strip/row from the upload address minus the image's pixel start, crop the same window from the
  HD picture and register a texel scale so the game's UVs (in its own texels) still land right.
  Forget the scale when the normal path reuses that GL texture.

## Scripted cameras, screen-space light shadows, normal targets (lesson)

- **A scripted shot inside gameplay** (e.g. a nap on a bed): OpenGOAL's external camera has a
  `'locked` mode: set `*math-camera*` trans, a look-at matrix in `*save-camera-inv-rot*`
  (`forward-up->inv-matrix`), `*external-cam-mode*` = `'locked`; reset it to `#f` in the state's
  `:exit` so any way out of the state gives the camera back.
- **Shadows for a spot light far from the surface** (headlights): reuse the point lights' screen-space
  march but cap the reach (~12 m) and stop a few meters short of the lamp: the vehicle carrying it is
  in the depth buffer and would shadow everything.
- **Before adding normals to a renderer**, check what reads them: the composite already used an
  analytic normal for the sea and skipped the G-buffer there, so the visible gain was small. A
  surface drawn with depth test ALWAYS under the level (the far sea) must not write the normal target:
  later draws that write none (generic) would inherit it.
- Heredoc Python writing C++: `"\n"` inside the heredoc becomes a real newline in the C++ string;
  fix string escapes with the Edit tool.

## Profiling and auto quality on a vsynced renderer (lesson)

- **Per-pass GPU cost**: wrap each pass in `glFinish(); child node; pass; glFinish();` behind an env
  switch, and force the renderer's per-bucket sync; dump the profiler tree every few seconds. A pass
  with no finish after it leaks its cost into the next bucket's time (the "HUD" bucket looked like 11 ms).
- Toggling one setting at a time from a copied settings file (one game run per variant) showed no single
  feature dominating the big composite shader; the wins were whole passes (volume + GI ~1.7 ms).
- **GPU timestamps across a whole frame lie under vsync**: with spare time the GPU waits for the screen
  inside the frame, so frame start->end reads ~16.5 ms at 60 fps whatever the load. Only trust it while
  the frame rate is actually below target; measure the post pass alone (no waits inside) for headroom.
- **"The post costs 10 ms" can be the frame limiter's sleep** (Jak Enhanced): the frame's last commands
  sat unflushed in the driver while the CPU slept to 60 fps, so the GPU idled, then drew the tail after
  the sleep, and every timestamp up to there counted it (post 9.6 ms, real 2.3). `glFlush()` right before
  the limiter sleeps fixes timers and latency at no fps cost. To tell GPU-bound from CPU-bound, compare a
  `glQueryCounter(GL_TIMESTAMP)` with `glGetInteger64v(GL_TIMESTAMP)` read as the CPU queues it: the GPU
  running >4 ms behind = GPU-bound, <2 ms = it waits for the CPU (gate auto quality on that, not on
  timestamp spans the driver's downclock inflates). Test it with switches that redraw a fullscreen pass n
  times (GPU-bound) or busy-wait the render thread (CPU-bound); keep the test above the "loading" floor.
- **An RGBA16F frame "costs +5 ms CPU" = a PBO readback in the wrong format** (Jak Enhanced HDR scene):
  `glReadPixels(..., GL_RGBA, GL_UNSIGNED_BYTE)` into a pixel buffer from a half-float FBO makes the
  driver convert on the CPU, so each read waits for the GPU (48 one-pixel exposure reads = 4.9 ms). Read in
  the attachment's own type (`GL_HALF_FLOAT`; query `GL_FRAMEBUFFER_ATTACHMENT_COMPONENT_TYPE`) and
  convert halves yourself. When a format switch looks expensive, profile CPU per pass before blaming
  bandwidth. A second game instance on the same GPU makes GPU ms swing 6-14 ms: alternate A/B 3x.
- **Screen blend (`GL_ONE_MINUS_DST_COLOR`) breaks in a float frame**: past 1 the factor goes negative
  and subtracts light. The 8-bit trick that tamed big additive glow pools can't follow into RGBA16F, where
  the plain sum no longer clips and spreads as a wide saturated wash. Scale only the big quads with a
  constant factor (`glBlendColor` + `GL_CONSTANT_COLOR`, 0.7 in Jak 3's arena) and let the final
  shoulder roll the core to white; small lamp/thruster glows keep the full sum.
- **PS2-emulating shaders need a per-fragment clamp in a float frame**: they do `color *= 2` and rely on
  the RGBA8 target clamping each fragment (GL clamps source colour AND blend factors for fixed-point
  buffers). In RGBA16F a 2.0 alpha turns `SRC_ALPHA/ONE_MINUS_SRC_ALPHA` into add-and-subtract, HUD textures
  (minimap) go over-bright, orange flames go white. Fix once at shader load: rename `main`, append a
  wrapper that clamps the `out vec4` to 0..1; skip shaders that copy the frame (distortion, depth cue).
  Only additive sums of several fragments then pass 1, which is the point of HDR. Identical in RGBA8.
- **Auto quality** that works: step down only after ~3 s continuously under ~58 fps but above ~40
  (loading hitches are CPU and inflate GPU clocks); remember what each step saved in post-pass time;
  step back up when other + post + saved fits in ~15.3 ms, or after a minute at 60 fps as a retry.
- Measure at the same hour of the game: day vs night changed the same spot from 60 to 50 fps.
- **Even the post pass alone reads flat under vsync**: at 60 fps the driver lowers the GPU clock to just
  meet the frame, so a 1.3 ms cheaper composite still showed "post 13 ms". Compare passes only in the
  glFinish profile mode (it drops the frame rate, so the clock is at full speed).
- A switch that zeroes named uniforms of the big shader just before its draw (type from
  `glGetActiveUniform`) measures each feature without new settings; but the auto quality moves between
  runs and changes which passes run, so pin the level or read the deltas as +-0.5 ms noise.
- Cheap wins in a big hand-written composite: a `sin`-based `hash2` inside gradient noise called ~20
  times a pixel -> an arithmetic hash (Dave Hoskins') saved 1.3 ms of 8.5 with no visible change;
  the occlusion + contact shadows at half resolution (depth-aware blur at half too, normals still from
  full-res depth) went 1.65 -> 0.95 ms, no halos; auto-quality levels past "passes off" that lower the
  game's internal resolution (85%, 72%) stretched by the final blit.
- **A pass that reuses an uber-shader behind a uniform branch pays the whole shader's registers** (Jak 3
  Enhanced clouds: `if (cloud_pass == 1) { color = cloud_march(); return; }` at the top of a 4000-line
  composite). Compile the same file a second time with `#define ONLY_X` inserted after `#version` (main
  calls only that function; the rest moves into an uncalled function and is stripped), and copy the
  values of its few active uniforms from the big program each frame (`glGetActiveUniform` list built once
  per program pair, `glGetUniform*v` -> `glUniform*`; 30 uniforms, no visible CPU cost). Same picture,
  0.75 -> 0.51 ms at 2560x1600. At that resolution the composite itself is 11-16 ms, and zeroing each
  feature's uniforms in turn finds only ~2 ms (lights 1.4, rock detail 0.4, water 0.35).
- **Find where an uber-shader's time goes by early exits, hot-reloaded in one run**: a script inserts
  `#if PROF_EXIT == k  color = vec4(c, 1); return;  #endif` before every top-level statement of main
  ~25 lines apart, then sets `#define PROF_EXIT k` per variant (hot reload, ~10 s each, pass timer read
  from the log); the curve of cumulative ms shows the hot stretches. Learned on the 13 ms Jak 3 composite:
  (1) compiling out *dead* code (night sky, a never-taken fallback march) saved ~0.1 ms, and skipping
  single executed pieces (PCSS taps, contact march, a 14-tap sky test) only 0.1-0.4 ms each: the cost
  is spread over everything that runs (a thousand cuts at low occupancy), not in a few lines;
  (2) the win was a **loop of dependent reads over a low-frequency term** (rays toward the sun: 10 x
  depth + cloud texel per pixel), moved to its own slim program at quarter size (`#define ONLY_RAYS`,
  R16F, bilinear read back): composite 13.3 -> 12.35 ms for a 0.2 ms pass, same picture. Look for that
  shape first; (3) NVIDIA `#pragma optionNV(unroll none)` +1.5 ms, `optionNV(inline none)` +10 ms,
  `unroll all` / `fastmath on` no gain: keep the driver's defaults; (4) NVIDIA's `glGetProgramBinary`
  no longer carries the assembly or register count, only its size.
- Before GPU culling / Hi-Z for a PS2-era scene, measure: all the geometry buckets together were ~4 ms
  against 8 ms of post; the work belongs in the post pass.
- Rock detail over a game's cliffs, as AAA terrain does: each tiling size only within its own distance
  band (1.6 m tile to ~45 m, 7 m tile to ~160 m), past that only a soft macro light/dark noise; a huge
  tile (30 m) printed a repeated pattern on far faces that fought their own texture.
- Mountain shadows in a sunlit haze from the screen: in the god-rays pass (half res) march ~24 taps
  toward the sun's screen point (away from the anti-sun point when it's behind), count far surfaces
  closer than the pixel; exclude near things (no shafts from the player) and anything kilometers away
  (the game's sky clouds write depth); output in the shafts texture's alpha, blur 5 taps when reading.
- **Plan perf work from the profile mode, not from the vsynced log**: "post 12.9 ms of 15 ms GPU"
  under vsync was the downclocked GPU; in the glFinish profile the whole post was 2.4-3.0 ms and the
  4000-line composite 0.6-0.9 ms. Screen-tile culling of its 32-light loop (Jak 3, CPU-binned masks
  in a `uvec4[144]` uniform, `findLSB` loop) measured 0.00 ms gained: at that count the loop is no
  bottleneck. Toggle such a switch from the tuning file and split the profile lines by switch time.
- Reusing a flag slot for a new light class (alpha 2 = "flash" in a list where branches test
  `a < 0.5`) silently moves the new lights into the *other* branch (wrap lighting, no shadow), and the
  feature's "off" no longer equals the old code: the A/B baseline lied (floor 59 vs 36). Make every
  existing test treat the new value as before, then check off == old.
- A flash (explosion) under a lamp list's soft ceiling (`added /= 1 + k*max(added)`) can't light a
  torch-lit room more than a torch: give it its own accumulator, on top of the lamp term, with a much
  higher roll-off.
- Golden-hour "black slope" in the desert was not the sun shadow (shadows off changed nothing): stage
  views showed four multiplies stacking on one material class (rocky ground's low-light x0.5, relight,
  stop-down, dark-part deepening): x0.3 of the game's color. A floor relative to the game's own color
  (`max(c, raw * 0.75)` by the hour, by tags) fixes it without touching sunlit ground.

## TAA goes after every depth-based post effect (measured)

- If TAA resolves the raw scene and a later composite builds AO, shadows, lights or procedural
  ground detail from the *jittered* depth buffer, those edges move a fraction of a pixel every frame
  and nothing averages them: thin things (grass blades, pebbles) flicker, and turning TAA off "fixes"
  it. Resolve TAA on the finished composite instead (blit the composite out, resolve, blit back).
- Measure flicker objectively: camera and character still, burst of 8 window captures, mean
  per-pixel |frame[i+1]-frame[i]| over the ground (mask the character and HUD). Cycle the variants
  inside one run (env switch that changes mode every 6 s and logs it; capture right after each
  switch). Jak 3 desert: early 1.40 / late 0.30 / off 2.11; pixels changing >8 levels 2.1% -> 0.16%.
- Half-res AO read with plain bilinear also bleeds across depth edges: upsample it with the four
  texels weighted by depth similarity to the full-res pixel.

## Bright desert ground: exposure, not a highlight squeeze

- Compressing everything above the mid tones (a strong "shoulder") kills the ground's own variation:
  the sand reads flat and still looks overexposed. Darken the sunlit ground with a multiply that
  depends on sun height (keeps relative contrast), keep the shoulder only for near-whites.
- A per-zone grade with gain > 1 and high contrast is the usual culprit for burned-out noon; hue-based
  recolors (olive -> sand) must cap saturation at a sand's (~0.3), or the yellower patches turn
  orange in blotches and bands; pale near-white slopes need their own branch (no hue to key on).
- Characters in a cast shadow: the game lights them fully with its own lights (no shadows), and a
  composite that only looks the shadow map up on faces toward the sun leaves the rest lit, so at golden
  hour Jak glowed inside a wall's shadow. Look the map up ~70 cm toward the sun from every character
  pixel (past the body's thickness) and take ~0.85 of that shadow off. One lookup, no measurable cost.
- That lookup point (70 cm toward the sun) sits inside the body for legs and hips at a high sun: the
  character shades itself. Better: test the map at the pixel with a bias of ~1.6 m along the light
  (`s.z - gap_m / depth_span_m`): only casters that far count, so the own body, a shoulder pet and
  the screen-space contact march stop counting. And never give characters the land's shade tint: a
  lilac shade (takes much more red than blue) turned yellow hair and an orange sidekick olive green.
  A neutral tint at noon, toward brown at dusk (darkened yellow under a cool tint also reads olive);
  less shade under a high sun (bounce from the bright ground), deeper as the sun gets low.
- Check the shadow debug view before "fixing" a character shadow: here a "Jak in open sun" was really
  inside a 12 m rock's shadow (gap view: red/green/blue = 2/20/200 m to the caster); only the colour
  of the shade was wrong.
- Game glows and torch spawners turned into dynamic lights must fade out in full daylight, or they lay
  bright colored pools with hard shadows on sunlit ground.
- Far cloud "cards" (sky geometry kilometers out) need the same sky treatment at night/dusk as by day,
  or their sharp painted silhouettes drift across the dim sky.

## Matching a reference picture fast

- Don't restart the game per attempt: hot-reload the post shaders (poll the files' mtime once a second,
  compile, swap the program only if it compiled; uniform locations looked up per frame) and keep the
  tuning values in a hot-reloaded JSON. One boot, then ~10 s per attempt.
- Sweep a value inside the same run (rewrite the JSON key, wait for the easing, capture; restore at
  the end) and judge all variants on one sheet.
- Score each zone as the Lab delta E of its mean color against the reference AND against the last
  accepted shot, flagging zones that got worse: stops fixing one zone while silently breaking another.
- Check the framing automatically, on edge maps rather than luma (a lighting change drops luma
  correlation like a moved camera does).
- Before relighting to darken a region, ask whether it is dark in the reference because of the
  material (a rock texture) or the light. Lowering the sun to shade a "slope" darkened the flat plain
  that the reference keeps bright: a content problem cannot be fixed with light.
- Hold everything that moves still for scored shots (a test switch pinning the cloud time): drifting
  cloud shadows swung a zone's delta E by 10+ between identical shaders and hid real changes.
- After tuning one hour (golden), shoot another (noon) in the same run: effects keyed to a material tag
  but not to the hour (darkening a rocky ground) regress the rest of the day silently.
- A tiling detail picture laid over a flat ground shows its tile as a grid. Use it small and rotated
  (two sizes, turned differently), keep its dark crack lines faint (asymmetric gain) and carry the
  larger variation with noise; a relief from its finite-difference gradient lit by the sun reads as 3D.
- Tags packed in the normal's length get blended at alpha-blended edges: lengths between two tags are a
  mix, so fade the effect over the gap instead of thresholding (hard-edged patches otherwise).
- When the reference is backlit and the game's sun is not, light far objects by the sun's glow bearing
  (a low sun where the sky glows) instead of the scene's sun: faces toward the camera fall into shade.
- A relief from a tiling crack picture's gradient still crosses into a hatching up close: take the height
  from smooth noise lumps (half a meter and more) and keep the picture as a faint crust on them.
- Impostors (flat quads of a model's pictures) miss the shade the model's blades or stones cast on each
  other: the detailed copies read dark, their far pictures bright puffs. Darken the picture toward its
  foot. Check which batch flag a fix keys on (a "foliage" flag that was never set made it a no-op).
- A hard-edged "phantom" shadow: bisect its casters before fixing the receiver, with a test switch
  that skips a level, then a tree, then a draw range (one build, then restarts only). Here the culprit
  was a real building behind the camera. Things that should never cast: alpha-blended draws (veils,
  decals), water, envmap second draws. Not alpha-tested ones: in Jak 3 every draw has the test on, so
  dropping them dropped every static shadow (and only looked like a fix).
- When the reference lights its mountains from a side the game's sun isn't on, sweep a rotation of
  the bearing used to light them (here +57 degrees won); don't move the warm backlit glow with it, that
  put the glow on the mountains in view.
- An exposure cut for a bright ground (the high sun) applied evenly blackens the dark things (rocks):
  scale it by brightness, and keep it out of hours tuned separately (the low sun).
- A single scored shot can mislead about distance gates: a "far" fade already at 1 for a big far
  rock makes threshold sweeps change nothing. Paint the tags/gates in debug colors before tuning.

## Depthless sprites in post: flames, glows (lesson)

- A transparent sprite (a torch's flame) writes no depth or normals: every post effect shades it as
  whatever is behind it. In front of a palm trunk in shadow it got the trunk's sun shadow, SSAO
  and tag-based recolors: dim, green-blue, see-through. It only showed with something dark behind.
- Don't trust the game's object list to find them: not every flame is a particle spawner (the
  desert's torches weren't). Log the names/distances the hook receives before assuming the mask
  works; a debug overlay of the mask (`c = vec3(mask)`) plus one of the raw scene color settles it
  in two shots.
- A color mask that works: the raw pre-post color, very bright (luma > 0.85), full red, yellow to
  white (g >= 0.9 r, b <= g), and NOT over a land tag (sunlit pale sand matches the same color).
  Then at the end of the composite put back the raw color (`mix(c, raw, mask)`), not `max(c, raw)`
  (max keeps the blue tint).
- Hot-reload pitfall: editing GLSL with PowerShell string replacements, a `\n` inside a single-quoted
  string stays a literal backslash-n: the new code ended up inside a `//` comment and silently did
  nothing. Grep the result after a scripted edit.
- Effects recovered as "scene after sprites minus scene before" (to boost them by day) also catch
  **blended dust and smoke**: a tan puff over darker ground gives a warm, saturated difference, so a
  chroma or brightness test can't tell it from a flame (tried: it still glowed as an orange orb). What
  works: clear the frame's alpha to 1 right before the sprite buckets (color mask alpha-only +
  `glClearBufferfv`, scissor off), and draw the normally blended non-flame sprites with
  `glBlendFuncSeparate(SRC_ALPHA, ONE_MINUS_SRC_ALPHA, ZERO, ONE_MINUS_SRC_ALPHA)`: alpha becomes
  1 - their coverage. Added light (`ONE, ONE` / `SRC_ALPHA, ONE`) only adds to an alpha that is
  already 1, so it never marks. The post-sprite copy then carries the mask for free; leave marked
  pixels in the scene's grade (composite and bloom key alike).
- Sky glows (sun, moon) must stay out of that recovery: the weight's threshold cut in at the glow
  quad's edge and the gain saturated it, the sun became a purple diamond. Give sky pixels (depth 0
  or km away) weight 0; their glow then comes back as drawn with the rest of the sprites' difference.
- A blown light shape on water: give every reflection term its own test switch (lamp columns,
  far-beacon columns, screen/RT reflection, mask view) and shoot them in one run. Here the "SSR
  rectangles" were the far beacons' columns: near beacons summed with no occlusion and no roll-off.
  Mask them with the SSR hit (a wall in front hides the lamp) and soft-saturate the sum.
- Before blaming the TAA for a missing 1 px lamp (the jitter draws it on only some frames), shoot
  the same spot twice with the history off: tower beacons blink, and a single "TAA off shows it"
  pair proved nothing.
- Characters spared from a grade step (the land's evening deepening) and see-through cloth restored
  from the game's own color both skip the shadow's darkening: in a wall's shade Jak's hair and Daxter
  stayed sunlit. Darken character pixels by their shadow once more after the grade, last.

## Small traps (lesson)

- `far` and `near` are Windows macros: a variable or parameter with that name breaks the build in an
  unrelated-looking way; a build script that echoes its exit can still "succeed", so grep the log for
  ` error[: ]`.
- A NaN in a history buffer (clouds, TAA) stays forever and grows into a black block: guard every fetch
  and every result with `isnan`/`isinf` and fall back to "nothing" (alpha -1), not to a color.
- Shader hot reload only runs when its env switch is set in the test script; without it a "fixed" shader
  silently isn't the one on screen.
- Finding which pass draws an artifact without editing code: measure it as a number (e.g. a dark row =
  row mean minus the mean of rows +-2, over the affected columns) and compare it against vanilla and per
  env switch, one short boot each (~28 s); then bisect the composite's uniform groups with a "zero group X
  every 3 s" probe, capturing once a second and reading the dips (the probe starts ~10 s after the first
  frame, so a dip's slot is ambiguous: test the suspect alone, a toggle every 3 s shows as alternating
  values). Then open the pass's debug view. Jak 3 Enhanced: dark ground rows at fixed screen heights were
  SSAO (`JAK_ENHANCED_AO_DEBUG=1` showed them), only made visible by the point-light term it multiplies.
- A black blotch over a transparent effect (Jak 3 arena's light shaft): check the normal target's tag
  length there. A draw that blended into it left vectors longer than any tag (> 1.02); SSAO took them for
  the surface's normal and returned 0.07. Treat |n| > 1.02 as "no normal" in every reader (AO, GI,
  composite), then find the writer. Locate the stage cheaply: a `tune_stage` uniform plus one line per
  top-level section (`if (abs(tune_stage - K) < 0.5) dbg_c = c;`, final `c = dbg_c`), swept through the
  tuning file in one run, mean of a crop per stage: the drop showed at the AO multiply (159 -> 52).
  Commit with those lines stripped (tag them `// STAGEDBG`, filter them out of the staged blob, LF only:
  hashing the CRLF working file rewrote every line).
- Night skies that smooth the game's sky (painted cloud cards) also erase the lights drawn over it
  (beacons, searchlight beams). Keep the sky copy by night too and add back `max(scene - sky copy, 0)`
  where it is brighter than the sky, as light after the stars; replacing the pixel instead drew a dark box
  around the glow, and a sharpness test kept only a hollow ring of an even core.
- A sky glow kept out of an effects' gain and re-added as `after - before` loses its core where the sum
  clipped to white (almost nothing left to add): keep at least white where the copy after the sprites is
  clipped and they brightened it, and drop the faintest light (its quad's edge shows over a new sky).- **Brightness vs a reference build: pin the hour, shoot both builds the same way, twice.** A tour that
  jumps 12->18->22h and shoots 12 s after each jump gave the same build 53.9 then 59.3 luma at desert 22h
  (dark pixels 12% vs 2%), and Spargus 18h 33.6 then 22.9: transients, not code. One boot per build with
  the hour re-set every 15 s and a `base` shot at the start and end of each spot (drift +-5%) made branch
  vs main comparable to ~2% (Jak 3: arena 20h 62.0/61.9, desert 22h 47.5/46.6). Bisect the branch's
  tuning switches in that same boot (one tune.json write + 2.5 s per variant, ~4 spots x 10 variants in 8 min).
- **Multi-bounce AO brightens the whole picture**: Jimenez's fit returns more than the grey AO for any
  albedo over ~0.3, so a "color of the crevices" change lifted a night scene ~5%. Keep its hue only:
  `ao_mb *= ao / luma(ao_mb)`.
- A night that spares "what's bright in the game's own picture" (to save a light shaft that AO/shadows
  had dimmed) needs its own, higher threshold than the composite's: from 0.4 it also spared every
  lamp-lit floor (+7%); from 0.6 the shaft alone.
- A low-sun "never darker than x of the game's color" floor must skip cast shadows: weight it by
  `1 - shadow * smoothstep(0, 0.1, N.L)` inside the shadow-map block (where N.L and the shadow are in
  scope) and carry that weight down to the end of `main()`.
- Uniform budget: an experimental `uniform uvec4 x[144]` on a composite already at ~860 vectors risks the
  1024 minimum of Intel/Mesa. Put it behind `#ifdef` (off by default); the C++ `glUniform*` on location -1
  is a silent no-op, so nothing else changes.

## Per-pass GPU timers, light columns, clipped pools (lesson, Jak 3 Enhanced, Nov 2026)

- **Time every pass with timestamp pairs, not the frame's "post" interval**: two `glQueryCounter(GL_TIMESTAMP)`
  per pass in a 4-frame ring, read only when `GL_QUERY_RESULT_AVAILABLE` (never wait; timestamps nest, unlike
  `GL_TIME_ELAPSED`), one log line every 5 s. Jak 3 at 640x360: the named passes summed 1.3-1.7 ms
  (composite 0.7, shadow near/far 0.25 each, clouds 0.1) inside an 11.4 ms "post" interval measured the same
  way: the interval is mostly the GPU idling for the CPU's submissions and the vsync clock, not shading.
  A plan to save 2-4 ms by halving passes would have saved < 0.5 ms; measure before planning perf work.
- **A translucent light column the game draws over a wall (Jak 3 arena shaft)** vanishes under post shade,
  AO and dusk grade: the wall behind is taken for the surface. Its blended draw leaves the normal target
  longer than any tag (|n|^2 > 1.04): there use `max(c, game picture - effects)` (gated by the game
  picture's luma > 0.3-0.5, decal strips mark it too). Restored the beam, nothing changed in the desert.
- **A jagged, blobby edge on a bright additive pool** (arena sun pool at dusk) is the 8-bit target's clip
  contour: where floor + pool >= 1 the copy holds 1 - floor (the texture upside down). Toggling the night
  keep, the effects' gain, a softened threshold or a mip of the difference changed nothing; it needs an
  RGBA16F scene target. Check the clip mask (`smoothstep(0.94, 0.99, after)`) before tuning thresholds.
- A "night glitch" colour can be an Enhanced feature's own light: Jak's desert lantern (14 m, orange) and
  placed torches (13 m) turned moonlit ground salmon. Give such lights tuning keys (reach, strength) and
  A/B them in one run before suspecting the grade. Palace "glowing blob with no source": shoot vanilla at
  the same spot first; it was the game's own glow.
- **A warm light's hue at night lives in the night branch, not in its reach**: Jak 3's lantern/torches at 9 m and
  x0.6 still left the moonlit ground salmon. Stage views (before night 51,65,88 -> after night 19,25,34 -> after
  lamps 98,72,66) showed the lamps' "own colour, warmer" term times orange light dominating the darkened blue.
  Fix: the faint part of the summed light (luma < ~0.9) loses its hue toward the moon's, as dim light does to
  the eye (Purkinje); the core by the flame stays warm. Desert box 96,65,56 -> 66,66,82 (vanilla 52,69,92).
- **Look at the mask view before tuning a gate**: an arena column's "crushed dim outer third" was the wall
  beside the column (the draw's mask ended where vanilla's column ends); lowering the luma gate did nothing.
  What softened the cut: the wall within ~13% of the screen of a bright mask pixel never darker than the game's
  picture x0.8 x a falloff (8 spiral taps turned per pixel/frame, TAA-averaged).
- Moon glints from `sky_sun` (the moon at night) showed nothing at Haven port 22h: the moon was behind the
  camera (reflection dot ~0, read from a debug view). Check where the light is before writing a glint.
  In Jak Enhanced's composite `clouds.w` is the night, not overcast (`clouds.y` is the cover).
- World.json's `golden` is not a dusk-only knob: it lowers the sun all day, moves the midday elevation and
  turns off dawn fog. A dusk-only grade for a city needs its own key.

## Dusk colour casts, cloud shade, GTAO pitfalls (lesson, Jak 3 Enhanced, Nov 2026)

- **A whole frame turning navy at dusk is many small cool pushes compounding, not one bug.** With the sun low the
  whole street is in the post's shade, so every "shade is cooler" tint becomes the frame's colour: the shade tint
  (more red than blue taken off), the cloud shadows' tint, and the warm grade's split-tone
  `warmth * (1, .25, -.75) * (luma - 0.35)`, which for a dark frame *cools* everything (dusk adds warmth, so dusk
  went bluer). Stage views showed each step at x1.1-1.15 blue/red; together frame B-R 19 vs the game's 4. Fixes:
  a warm grade leaves the shadows alone (`luma < 0.35` part x0), shade/cloud tints neutral as the sun goes down.
- **Gate "low sun" by the clock, not the area's sun height**: area looks clamp the post's sun (max elevations), so at
  19h it still stood ~20 deg up while the game's light was full dusk; an elevation-based fade did nothing until a
  `dusk` uniform (the hour ramp) was passed to the shader. Read the value in a debug view before tuning a gate.
- **A cloud only takes the sun away**: multiply cloud shadows by the sun-lit share (`mix(0.3, 1, sun_lit)`), or they
  stack on the sun's shadow (arena walls x0.65 x0.69 -> black).
- **Reproducing a scout's dusk shot**: `JAK_ENHANCED_MENU_SCRIPT` hour requests are integers (`'18.5'` -> 18), and
  game time runs ~1 h per 100 s: the glitch lived in 18.3-19 h and appeared 20-30 s after "hour reached". A direct
  boot at 18h looked fine. Pin the nearest integer hour that shows it (repeat every 15 s) and bisect there.
- A slums/arena spot with a fight is noisy (explosions, camera knocked): interleave A/B several times (n,o,n,o) and
  read the pattern, not one pair.
- **GTAO port pitfalls** (XeGTAO naming): the low horizon on the +offset side is `cos(n + pi/2)`, on the -offset side
  `cos(n - pi/2)`; swapping them made the AO view 71 instead of 155 (everything half-occluded). Take the slice's
  view-space direction from a real point at the same depth (mirrored view spaces). On a game's coarse depth, open the
  horizons by ~7 deg as the old Alchemy bias did, or grazing ground turns grey toward the horizon. At half res it cost
  nothing measurable (ssao pass 0.09 ms both).
- Interiors: fire/glow light strength keyed only to the clock left noon temples flat; a per-level "enclosed" list
  (plus indoor zones) giving night strength by day added the warm floor pools at no GPU cost.

## Floors after the grade, windows indoors, fog under the camera (lesson, Jak 3 Enhanced, Nov 2026)

- **A "never darker than x of the game's colour" floor goes last, not mid-composite.** Placed before the golden
  block and the per-channel contrast S-curve, its blue was taken again (curve on B=0.18 -> 0.09): arena wall
  69,51,29 (game) -> 33,24,13 orange. Last step: a luma floor whose colour is the game's, taken over by how far
  the post fell under it (`mix(c, fl * max(lc,lf)/lf, w * smoothstep(0, 0.3, (lf-lc)/lf))`): 49,35,20, hue = vanilla's.
- Stage views (`tune_stage` snapshot after each top-level step, crop mean per stage) find the step in one run;
  a per-channel S-curve and gain/lift are the usual saturation/hue culprits at low light, not the tint you suspect.
- **Interiors with windows onto the sky** (palace honeycomb): the post's sky filled the panes between the lattice
  lines, then bloom on itself (+40%) and eye adaptation (+20%) blew them white. Under a roof (per-level
  "enclosed" list) keep the game's own sky pixels (depth 0) at the end, and let adaptation's lift spare bright
  pixels (`mix(ea, 1, smoothstep(0.5, 0.9, maxc))`). A wider sharpness ring for the sky-keep test did nothing.
- **Height fog relative to the camera explodes when looking down** from a dock or cliff: `exp(-dy*t/H)` grows
  past the ground (15 m over the sea: x8) and the whole sea goes one opaque slab with a hard top edge. Stop the
  density growing a couple of metres under the camera (analytic: integral to the floor + rest at the floor's
  density). Waves came back (std 6 -> 12). Reproduce with the weather that has the mist, not a clear script.
- Morning lime/orange ground: cap a pixel's saturation at ~1.1x the game's own (`(max-min)/max`), weighted
  by the morning; the desert's designed peach morning moved only 2-3 levels.
- Night ground gone grey-lilac: at the end move the dim land's hue to the game's moonlit one at the same
  luma, fading out over luma 0.3-0.6 so lamp cores and flames stay warm.
- A "one-frame blob" in a street with a fight: interleaved bursts with the effects off (`fx.off`) still spiked;
  the brightest frames were a passing hover car's thrusters and enemy shots. Look at the spike frames before
  writing a temporal fix.
- **Caching far shadow maps**: keep each map's own matrix and read it with that one (never the new matrix over
  the old map); snap its square in steps of N texels (still whole texels); redraw on square move, depth window
  slide > 5%, light step, a generation counter bumped when a level's casters load/unload, or max age. Log
  redraws per 300 frames: desert parked 8-21 of 300 vs 150 every-other-frame; shadow bucket 0.35-0.85 -> 0.15-0.27 ms.
- PowerShell: `& script | Select -First 1` **stops the script** after its first output line (pipeline stop):
  a sweep died after launching the game, no shots, the game left running. Use `| Out-Null` or `Select -Last`.
- A "stale binary" claim from commit times: compare the sources' mtimes with the exe's; the C++ was edited and
  built before it was committed.

## Player brightness sliders without a new look (lesson, Jak 3 Enhanced, Nov 2026)

- Exposure per time of day = one `vec4` uniform: gain weighted by day/twilight/night factors, shadow
  lift, night fill. Send the gain **as an offset from 1** (`day*(b_day-1) + tw*(b_dusk-1) + ...`): neutral
  sliders give an exact 0 and the shader's `if (u != vec4(0.0))` skips the block, so the default is
  pixel-identical (a `day*1 + tw*1 + night*1` sum is 0.99999994, and an unset uniform is 0 = black).
- Keep it moody: gain tapered on bright pixels (`mix(g, 1+(g-1)*0.35, smoothstep(0.5,1,maxc))`), a toe
  `c *= 1 + L*(t/(y+t))^2` (t ~0.09: black stays black, mids barely move), a tiny cool additive only by
  night. Place it right after the eye adaptation, before the shoulder.
- Measured (desert 22h, mean luma /255): neutral 58, gain 1.3 + lift .2 -> 76, gain 1.7 + lift .4 -> 99;
  noon barely moves (bright sand sits on the shoulder): a day slider needs bigger values to show.

## Weather veils, flight, dither, a float frame (lesson, Jak 3 Enhanced, Nov 2026)

- **A "haze only in flight" can be the weather's cycle, not altitude**: the scout's ground shot (clear) and flight
  shot (beige veil, rocks chalk white) were different phases of a 4-minute changing-weather cycle (a sandstorm
  spell). Pin the weather for every A/B (a weather script: clear, or the storm itself) before bisecting.
- A volumetric dust/fog that takes "the ground" as a few metres under the camera fills the whole way down with
  its densest air once the camera flies: take the ground as the ray's end when it is lower, thin the density
  above the layer, and count only the layer's thickness of a long downward ray (`dist * H / max(drop, H)`).
- **Material relights applied after a veil brighten the veil itself** (x1.2-1.6 "sunlit rock" on dust-covered
  pixels = chalk white): keep the colour before the relight block and mix it back by the veil's coverage.
- Stage views found it in one flight: 12 `tune_stage` snapshots swept from the tuning file every 1.6 s, one
  sheet of 6; the jump sat between two snapshots 560 lines apart (the weather block).
- **Output dither**: a triangular +-1 step from two interleaved-gradient-noise samples, turned every frame, at the
  composite's 8-bit write; a TAA whose RGBA16F history is blitted into the 8-bit frame needs its own (else the
  smooth average bands again). Zero mean, so the history averages it out. Equal neighbouring sky pixels 57 -> 44%.
- **An RGBA16F game frame behind a live switch**: give the Fbo a format flag and re-make it when the tuning value
  changes (also the post's scene copy and the before/after-effects copies, or they clip again); A/B in one run.
  The clipped additive pool on a bright floor became a smooth falloff with its texture. In the float target the
  glow sprites' quads write alpha > 1 (debug view `alpha > 1.01`): clamp before trusting DST_ALPHA blends.
- Characters crushed at a low sun: a luma floor at x0.5 of the game's own colour (its hue), weighted by the
  low sun and off by night, last in the character block; merc props share the tag and get it too.
- .NET file calls (`[IO.File]::ReadAllText('rel\path')`) resolve against the process's start directory, not
  PowerShell's `cd`: always pass absolute paths.

## Random weather veils, cached near shadows, HDR cost (lesson, Jak 3 Enhanced, Nov 2026)

- **A glitch that "doesn't reproduce" may be a random weather spell**: Spargus' noon orange veil came from a
  sandstorm spell (32% odds per spell in the desert zone, a random offset per visit), not from the haze code
  the scout blamed (`tune_haze_layer` 0/1 changed nothing). Give spells a live test key (`weather.test_spell`)
  and log the post's dust and the game storm's intensity on change (per tenth): the cause is then one log line.
  Fix: a walled town scales the dust (`weather.town_dust` 0 in `was*` levels): 135,112,92 -> 95,82,70.
- **Characters float at a low sun when the sun map replaces the game's own shadow**: the map's character
  shadow is a long band off the feet. Keep the game's short projected shadow (Shadow2) too below ~25 deg.
- **Near shadow map cache**: keep the static part (all but wind-blown trees) in its own depth map, redrawn on
  snap move / depth slide / level change / age (the far map's rules), then each frame `glBlitFramebuffer` it
  into the live map and draw only the trees and characters. The 4096^2 DEPTH32F blit costs ~0.3 ms by itself,
  so it pays only where the static draw is heavy: forest 1.66 -> 1.05 ms, a town 0.51 -> 0.45. Frames on/off
  differed less than two consecutive frames (diff the pair *and* a same-setting pair to know the noise).
- **An RGBA16F game frame is not free**: +1.4 ms renderer time at 640x360 (3.8-4.2 -> 5.2-5.7 ms/frame,
  repeated A/B), for a partly better clipped pool. Additive glow quads also sum alpha past 1 there: give the
  glow draw `glBlendFuncSeparate(ONE, ONE, ZERO, ONE)` so DST_ALPHA readers see what the 8-bit frame had.
  Before a "stopgap in the LDR path", check the blob isn't in the game's own frame: `fx.off` changed nothing.
- **Thresholds on values mid-composite**: a "compress above luma 0.35 x night" knee never fired: after the
  night darkening the pale slum ground was luma ~0.04 (exposure and grade lift it later). A debug view
  (weights in R/G/B, written at the end of main) showed it in one shot; knee 0.025 then worked (-10%).
- Fights make A/B noisy: use the same-frame split (`tune_x 2` = right half) and pick measuring boxes away
  from coloured effects (magenta goo made a "no change" box).

## Clipped glow pools, late compression, nested profiler nodes (lesson, Jak 3 Enhanced, Nov 2026)

- **A big additive glow over a lit floor clips in the 8-bit frame** (Jak 3 arena light column pool: vanilla
  too). Without an HDR frame, blend the big quads as a screen, `glBlendFuncSeparate(ONE_MINUS_DST_COLOR,
  ONE, ONE, ONE)` (D + S(1-D)): a soft knee, the floor's texture stays. Choose per quad by its screen
  size (GS x span / 512, y / 256; >= 0.2 of the screen) so small lamp/thruster glows keep the plain sum
  and the effects' day boost (after - before) still finds them. Pool 205 -> 173 at 19h, no cost.
- **A darkening mid-composite can be undone by what follows**: the night "pale ground" compression at
  -90% came back as -5% after eye adaptation and the lights. Mark the pixels where the conditions are
  known (a weight in a global), apply the compression on the final values just before the shoulder.
  Check the weight's parts in a debug view first: the night factor's gate (0.3..0.8) was only ~0.5 at
  21h. Slums flagstones 157 -> 87, walls unchanged.
- `JAK_ENHANCED_ENEMIES=0 JAK_ENHANCED_POPULATION=0` quiets the city for A/B in Haven's slums (no fight,
  camera stays put).
- **Profiler nodes in a `std::vector`**: a timing macro that calls `prof.make_scoped_child()` on the outer
  node from inside a nested timed call adds siblings to the vector holding the still-open node: it
  reallocates, the scope finishes freed memory ("finish() not called on ..." spam). Bind the child as the
  wrapped call's `prof` (`[[maybe_unused]] auto& prof = node;` in the macro's block). Don't bracket passes
  with glFinish to profile: keep the timestamp-query timers on.
- Hour drift kills low-sun A/B: a menu script that pins the hour ends, and 30 s later the 18h long
  shadow is gone. Pin the hour for the whole cycle, and test hot reloads only inside the pinned window.
- Before extending a reflection's range, check it finds anything: Haven harbour 19h far water looked the
  same with water SSR capped at 80, 200 or 300 m (composite 0.76 ms all); the cap was not the cause.

## Pass timers that stop early, violet FX light, flattened night ground (lesson, Jak 3 Enhanced, Nov 2026)

- **A per-pass GPU timestamp pair can read 0.7 ms for a pass that costs ~9.5 ms.** On NVIDIA GL the end stamp
  after a full-screen draw is written before its fragment work finishes; the cost lands in whatever later span
  waits for that output. Jak 3's composite read 0.77 ms while a "tail-span" timer from its draw to the end of
  the post read 9.7 ms (total 11.8). A glFinish before the post left the total unchanged (not 3D spill, not
  CPU: CPU to the composite 0.6 ms). Bracket the big pass with spans up to the next dependent blit before
  trusting a "this pass is cheap" plan; old "0.00 ms gained" results read off such a timer are void.
- A heavy uber-shader near the constant limit: 144 extra `uvec4` uniforms failed on NVIDIA with
  `C6020 Constant register limit exceeded` (the shader silently kept its old version). Per-tile masks go in a
  small `R32UI` texture (`usampler2D` + `texelFetch`) instead; it costs a sampler, not constants.
  Every other per-pixel loop over screen-space points (far beacons with a pixel-radius cutoff) can share
  it as more channels (`RGBA32UI`, flags in one existing uniform): binning 64 beacons by the shader's own
  cutoff saved 0.5 ms at 2560x1600. Prove a culling mask by painting its bit count into the frame for one
  hot reload (and wait past the reload's compile time, ~11 s for a 4000-line shader, before capturing).
- **Many faint effect glows sum into a saturated light**: a dark eco cloud is ~12 violet glows (0.1, 0, 0.12)
  each; with per-glow damping they still lit Jak magenta. Cap the summed light per hue class (scale each by
  `min(1, N/count)`) and pale it toward its luma; also hold the bloom-based light spill's violet chroma and
  reduce it on characters (they stand in front of the cloud). Fights are random: alternate old/new every
  0.4 s through the fight's start in fresh boots and compare the peak hue share, not single frames.
- **A knee compression flattens texture**: a night "pale ground" press with slope 0.35 above a knee also cut
  the boards' grain to a third (one even sheet). Multiply the game picture's own local grain back on
  (`luma(px) / mean(4 taps 2 px away)`, clamped 0.6-1.4, weighted by the press): grain std 4.9 -> 6.0, mean unchanged.
## Painted window panes, a volume pass that never ran, finding a sprite by hiding textures (lesson, Jak 3 Enhanced, Nov 2026)

- **"Sky through the windows" may not be sky**: the palace honeycomb panes at 18h were a blended pane with the sky
  painted on, ~25 m away (debug view z/40 m, tag length): a depth-0 "keep the game's sky" fix never touched them,
  they were shaded, relit and bloomed as a wall (cream, drifting blotches). Their draw leaves the normal target
  over-long (the translucent-column test): under a roof keep the game's colour there too. Look at a depth/tag view
  of the glitch pixels before writing the gate.
- **A cheap feature riding on a gated pass can be dead twice over**: the volumetric pass ran only with fog > 0
  (fog is off on purpose) and the auto quality's first level sheds it (a 60 fps machine sits at level 1 because the
  post's idle tail counts as GPU time). Light-only in-scatter (8 lamps, 24 steps, half res: 0.09 ms) needed its own
  gate and the second level. Check the pass is in the "[enhanced] passes" line before tuning its look.
- A game light's reach is not a halo size: slum street lamps reach 27-30 m; as halos they washed a wall pale (frame
  mean 35 -> 49). Clamp the halo radius (6-8 m) and skip sky-sized lights; log reach/distance/colour once first.
- **Which sprite is it?** A temporary tune key that skips the sprite buckets whose texture name matches entry N of a
  list, cycled in one run (11 names x 4 shots, ~1 min), narrows a glitch to a texture without a rebuild per guess.
  Count a hue that flames don't share (lime: g >= 0.97 r) or flames swamp the metric. If the glitch is already in
  the raw game frame (debug view of tex_T0), no post gate will fix it.
- PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM: a commit message file made that way starts the subject
  with U+FEFF. Write it with `[IO.File]::WriteAllText` (no BOM).
## An albedo target, stacked haze, test weather (lesson, Jak 3 Enhanced, Nov 2026)

- A post that only has the lit frame can't relight properly: lamps multiply the night-darkened colour. A third MRT
  (RGBA8, texture colour before the vertex light, a = baked light luma / 2) beside the normal target fixes the
  input. Every shader that runs while the extra draw buffer is on must declare and write location 2 (0 = none
  for characters/water), or the target holds undefined values; renderers whose shaders don't (generic, grass,
  a blended water) mask it with `glColorMaski(2, false...)` where they already mask attachment 1, and the
  per-draw mask that keeps blended draws out of the normals covers it too. Cost measured: ~+0.4 ms GPU at
  640x360. Prove it with a split debug view first (right half = albedo / baked light): Jak and water black,
  textures unlit.
- Far ground lifted by four stacked haze layers (sun haze, golden glow, low dust, sand haze) went flat beige;
  no single term was the cause (each ~-10 luma when skipped). One debug uniform skipping each term in turn,
  then a cap on the block's total lift over the pre-haze luma (1.2x, hue kept) restored the relief.
- `weather.test_spell` acts only in weather mode 1 (changing): with `JAK_ENHANCED_WEATHER_SCRIPT=0:0` it does
  nothing. Boot with `0:1` to force a shower/overcast spell from the tuning file.
- Removing a line with an editor's exact-replace (old = "\n<line>", new = "") on a CRLF file joined the next
  declaration into a comment and the composite failed at boot (a failed composite at boot is fatal, not a
  hot-reload warning). After any line deletion, read `git diff` before relaunching.
## Scoping a look fix by level, area-scaled uniforms, locale in tuning files (lesson, Jak 3 Enhanced, Nov 2026)

- **A fix made for one place belongs behind that place's flag**: a night "pale ground" press made for the slums'
  flagstones (up-facing, away from lamp bloom) also took a third off every night level (desert 22h, port 21h).
  A 1-line C++ flag from the level name (`level.rfind("ctyslum", 0) == 0`) as a uniform kept it where it was
  meant: slums 38.9 -> 31.6, desert/port A/B diff equal to the same-setting noise. Cheaper and surer than a
  "brighter than its surroundings" pixel test.
- **Uniforms scaled by an area grade are not 0..1 factors**: `golden` = hour curve x the area's grade (desert
  0.5), so a gate `1 - golden` only halved a cap at 18h. Gate on the onset (`1 - smoothstep(0, 0.2, golden)`).
- **PowerShell on an Italian (comma) locale writes 1.2 as `1,2`** in string interpolation: a tuning JSON
  `{"tune_x": 1,2}` is invalid and silently ignored, so the "variant" shot is the old value. Pass values as
  strings ('1.2') and check the log's `shaders.tune_x = ...` line for every variant.
- Menu-script hour steps every 15 s land in the middle of a variant set: fit all variants of a point inside one
  interval (3-4 shots at 2.5-3.5 s) or the last shot shows the next hour/travel and reads as a huge diff.
- Before "adding" a light flicker or a specular occlusion, grep the CPU side too: glow-detected fires and manual
  lights already flicker (EnhancedPostScene.cpp), glossy/puddle reflections already had Lagarde occlusion.
  An extra occlusion on wet lamp glints measured within noise at the port after rain: reverted.

## Hi-Z pyramid for screen-space reflections (lesson, Jak 3 Enhanced, Nov 2026)

- Build it from the depth copy as R32F *view z* (not raw depth), with sky and the reflector itself (the sea's
  own depth) written as 1e30: rays then never stop on them, no per-step sky/sea test needed. Levels sized
  `size >> L` (floor); at an odd edge the last texel takes a 3-wide footprint so the shader can use
  `min(ivec2(s) >> L, lsize - 1)` and the last tile's far edge = the screen edge.
- Write level L while reading L-1 of the same texture: set `GL_TEXTURE_BASE_LEVEL = MAX_LEVEL = L-1` per pass
  (texelFetch lod is relative to the base level), restore 0..N-1 after. One FBO, re-attach per level.
- Traversal in screen pixels with 1/z linear along the segment: tile fully behind the ray (ray's far z <
  tile min z) -> skip to the tile exit, one level up; else jump to where 1/z reaches the tile's min, one level
  down; at level 0 a hit if just behind the surface, and reject surfaces nearer than the reflector (the
  rock the camera stands on). Clip the segment to the screen and to z > near first.
- Cost at 640x360: pyramid 0.06-0.1 ms, composite unchanged with 40 tile visits vs 32 linear steps.
- Texture units: grep every `tex_T<n>` in the big composite shader before picking one (28 was already the
  light-tile bitmask there: glslang said "redefinition"). Run `check_shaders.py` before booting: a shader
  that fails to compile at startup asserts the whole game.
- Before a staged "move pass X onto the pyramid" milestone, read the per-pass timings in a log you already
  have: the planned GTAO-on-Hi-Z step was dropped in 2 minutes because GTAO wasn't the shipping AO and the
  shipping SSAO was 0.07-0.18 ms at 640x360 (nothing left to save), and it ran before the pyramid was built.
  Short rays (0.5 m contact shadows) gain nothing either. Pyramids pay off for long rays only.
- PowerShell `.Replace()` on a .cpp with CRLF silently misses multi-line needles written with `` `n ``: use the
  Edit tool, or match one line at a time.

## Cheap ray-traced AO: 1 ray + reprojected history (lesson, Jak 3 Enhanced, Nov 2026)

- Traced AO depends only on the world point and its normal, so reprojecting last frame's result is
  exact for static geometry: rebuild the world point from depth, project it with LAST frame's camera,
  fetch an RG16F history (r = AO, g = view distance), reject when the stored distance differs > ~3 %,
  mix with keep ~0.9. 1 ray a pixel turned each frame (R2 sequence per frame on top of the per-pixel
  noise) matched 6 rays every frame, at a quarter of the cost (+0.06 vs +0.26 ms at 320x180 half res).
- Write the history as a second colour attachment of the AO pass itself (MRT): no extra pass.
- A pixel checkerboard (or 8x8-tile one) to halve traced pixels gave NO gain: the traversal is
  divergent, and once a ray is 1/pixel the reprojection + history fetch is most of what's left.
  Time it with a GPU timer query on that one draw, cycled inside one run: fps and the 5 s pass
  averages are swamped when another game shares the GPU.
- A resource cache keyed on "which levels are in use" must be cleared when the feature is switched
  off, or switching it back on finds the same key, skips the rebuild and runs with count 0.
- Judge it INDOORS before shipping, not in an open courtyard: in a hall (Hip Hog) the same 1-ray pass
  cost 8x more (+0.5 ms at 640x360: every ray hits something within its 3 m) and still looked the
  same as a good GTAO in the AO debug view. Short per-pixel rays only find corners SSAO already finds;
  the occlusion that matters indoors (a roof 5+ m up blocking the sky) is far and low-frequency, so it
  belongs in probes (sky visibility per probe), not in a per-pixel pass. Kept opt-in.
- First step toward probes, cheap and useful alone: a top-down **sky map** (rain occlusion) traced
  through the same BVH: one ray straight down per 0.5 m cell, 256^2 around the camera, a band of rows
  a frame into a back texture, swapped whole (0.01 ms). Store the first 4 surfaces from the top
  (continue each ray just past its hit), not only the topmost: for slanted rain the cover that counts
  is the lowest one over the point (an arch's underside at 3 m, not the roof at 15 m). Covered =
  topmost surface above point + gap; then 4 taps at (lowest cover - y) x 0.35 around: open if any is.
  Look it up offset 0.6 m along the normal, or every wall under an eave reads covered. Debug view
  (green open / red covered) first; most spawn points have no roofed ground, so proving it needs a
  hand-picked spot (arcade, market awning). Don't guess spots: let the map find them. A debug switch
  reads the finished map back once (glReadPixels, 1 MB) and logs the roofed floors nearest the camera
  (lowest surface, next one 2.2-12 m over it, over a whole 5x5 block); then teleport there. Expect
  false "floors" (under a pier deck, inside closed buildings: teleport lands black), so try 2-3.
- Probes on a game with **baked vertex light** (Jak 3, gfx-tech2 M2/M3): the baked light already holds
  the indoor darkness, and a deliberately dark look forbids adding bounce brightness, so the probes can
  only steer hues (characters' night rim by open sky, shade's sky-blue -> bounce hue under a roof).
  Both measured at or under frame noise (palace 12h: diff 5.7 vs 5.3-6.2 between frames of one variant,
  because that area's sun shadow strength is low) for 0.3-2 ms: kept opt-in. Judge "is the effect bigger
  than two frames of the same variant" before spending more milestones on it. The probe pass cost did
  not scale with rays (2 rays 0.5 ms, 8 rays 1-2 ms, 16 ~ 8): divergence and the per-level BVH restarts
  dominate. A finder spot can also land the camera looking straight down on Jak (no view of the cover).
- **Physical sun color** (Rayleigh lambda^-4 + Angstrom aerosols lambda^-1.3 at 680/550/440 nm over the
  Kasten-Young air mass, relative to the sun overhead, hue only with the old ramp's luma): map the area's
  haze to aerosols gently (beta 0.04 + 0.08 x haze); 0.2 x haze turned the desert's 18h sun blood red. Pin
  the hour while comparing (menu script hour every 10 s, 4 s per variant): the clock otherwise moves the
  sunset more between two shots than the variant does.
- **Physical sky dome, cheap** (single scattering over a flat layer, closed form per channel:
  `L = sum(tau_i P_i)/tau * m_v (e^(-tau m_s) - e^(-tau m_v)) / (m_v - m_s)`, Rayleigh + HG g 0.7 phases,
  white balanced on the sun overhead, hue only so the art's brightness and dark look stay). Two fixes
  are mandatory: cap the view air mass at ~10 (the flat layer's 38 at the horizon made the whole low sky
  deep red at sunset, even away from the sun), and add ozone's Chappuis absorption (300 DU:
  tau 0.004/0.027/0.001 at 680/550/440, along both paths): without it the morning's low sky goes
  olive-green, with it the twilight pink/violet appears on its own. Check offline in Python first (a table
  of hues by sun height x view direction), it costs seconds instead of game runs. Judge it against the
  user's reference picture by band: mean RGB distance of 3 horizontal sky bands, off 29/37/25 -> on
  10/23/21 at the reference hour, a measurable win where a side-by-side alone is taste. A `>= 10` debug
  that returns the hue x 0.5 shows little when the sky's luma is ~0.5 anyway: debug at full saturation.
  At dusk the game's own painted sky replaces ours (`game_w`), so a sky-dome change is invisible there.
- **Physical shade tint** (shade loses sun/(sun+sky) per channel, ratio from the shade's own darkness):
  match the darkening by luma, not by the plain channel mean (3.5% lighter noon shade). It came out equal
  to the hand-tuned desert lilac (b/r 0.676 vs 0.675): a hand tint already tuned to a reference is often
  physically right; measure the shaded crop's b/r against frame noise before replacing it.

## Measure GPU cost at the player's resolution, tile every light loop (lesson, Jak 3 Enhanced, Nov 2026)

- A 640x360 test window hides the GPU budget: post read 2.2 ms there but 15-20 ms at the player's
  2560x1600 (18x the pixels). Add a test-only override of the internal render size
  (`JAK_ENHANCED_TEST_RES=2560x1600`) so a small window still draws, and times, the real frame. Pin
  the auto-quality level while measuring (`JAK_ENHANCED_AUTO_MAX=0`), or it drops the resolution mid-A/B.
- In an uber composite, per-pixel loops over the light array add up even when each light is culled
  early: 4 loops x 32 lights cost ~2 ms at 4 MP, while the lamps' shadow march (the suspected cost)
  was 0.12 ms. Zero uniform groups one at a time (cost probe) before optimizing a guess.
- A screen-tile light mask pays off only when every loop uses it: grow each light's sphere to the
  widest reach any loop needs (highlights 1.6 r, air glow 1.5 r, halo angle as a fraction of
  distance) and walk the tile's bits with findLSB in all of them. Main loop only: -0.2 ms; all: -0.6 ms.
- An A/B pixel diff is "equal" when it matches the diff between two frames of the same variant
  (TAA jitter noise), not when it is zero.
- Another game on the same GPU (the user playing) inflates every absolute GPU time: compare variants
  cycled in one run, never across runs.- A flame the "is it a fire" test misses: dump the glows near the camera (Jak Enhanced `lights.dump <m>`
  in the tuning file) before guessing. Spargus palace braziers drew only 8-18 m warm halos, past the
  6 m size cap of a fire glow, so no flame mask and the grade dimmed the flame: count wide warm halos
  as fires with the flame size clamped (0.2x, max 2.5 m), behind a tuning key.
- Char look checks at golden hour need a backlit sunlit spot (desert-start 18h: Jak's shadow points at
  the camera); a street in shade shows nothing for a sun_lit-masked effect.

## Splitting an uber composite: what pays and what doesn't (lesson, Jak 3 Enhanced, Nov 2026)

- Before splitting work out of a big composite, test whether its cost is registers or work: move
  one costly feature into its own full-size program (same file, a define compiles only it) and
  compare the composite's drop with the new pass's time. Jak Enhanced's rock detail + sand ripples:
  composite -1.22 ms, own pass 1.21 ms at 2560x1600: pure per-pixel work, no occupancy win. A
  split pays only when the new pass runs at fewer pixels (cloud rays at a quarter: -0.75 ms net).
- Pack many per-pixel factors into one RGBA32UI target with packHalf2x16 (eight halves, one
  texelFetch), and `discard` the pixels the composite won't read, to save the write bandwidth.
- Refactoring inline code into a function with outs cost the NVIDIA build +0.15 ms: re-measure the
  old path after any refactor, not only the new one.
- Cheap A/B of "what if X were free": swap one helper's body for a trivial one by hot reload
  (a cheap gnoise: -0.55 ms), then decide if a real replacement is worth building. A bilinear
  lookup of the same noise (1024^2 R16F, 16 texels a cell, period 64 cells, exact at the lattice)
  kept only -0.12 ms: the fetch latency ate most of the ALU saved.
- No gain: Vogel disc taps turned incrementally instead of sin/cos per tap, and fewer PCF taps for
  narrow penumbrae. Zeroing uniform groups one at a time (cost probe) showed a 12 ms composite with
  only ~3.5 ms in nameable features: the rest is base cost spread over every pixel.

## Profiling an uber composite: exits lie, skips and compile-outs tell (lesson, Jak 3 Enhanced, Nov 2026)

- An early-exit bisection (`#if EXIT == k  color = c; return;`) does NOT measure each block's cost: every
  exit also strips the later code (dead), changing the register allocation. Jak Enhanced's sky block read
  1.7 ms by exits; skipping it at run time (`if (EXIT == k ? false : (cond))`) saved 0.2 ms, and
  returning early on every sky pixel saved 0.1. Measure with run-time skips of one block at a time, all
  variants hot-reloaded in ONE run with the baseline repeated (the GPU drifted 12.4 -> 13.1 ms in 15 min).
- A python helper that wraps every top-level `if (...)` of main() with `ENH_PROF_EXIT == k ? false : (...)`
  (matching the condition's parentheses across lines) gives the whole per-block table in one ~12 min run.
  Result there: no block over 0.4 ms except the sun shadows (1.25), rock detail (0.9) and sand (0.7);
  some skips came out SLOWER (+0.5 ms): the compiler's scheduling swings more than most blocks cost.
- Compiling out blocks that never run in the frame (water, wet, blasts, headlights, cutscene DoF) gave
  only -0.26 ms: register pressure was not the hidden cost either. A "lean" program variant chosen per
  frame wasn't worth an extra 1 MB program (and its gate failed anyway: the far sea, 5 lamp glows and a
  random dust veil were "on" in the plain desert frame; log the gate's uniforms before building one).
- What paid: temporal half-sampling of the half-resolution passes. Each frame takes every other tap
  (`i = frame & 1; i += 2`), the result averaged 50/50 with last frame's other half fetched at the same
  world point (view -> previous view as the TAA's, an R(G)16F history written as a second colour
  attachment, rejected when the stored distance differs > 3 % or after a cut). SSAO 0.77 -> 0.55 ms,
  one-bounce GI 0.53 -> 0.36 ms at 2560x1600; occlusion equal within 0.9/255.
- An A/B of shots taken a few seconds apart at dusk differs by the clock (the later shot darker): take
  the pair in both orders before blaming the variant.
- A block that costs 1.25 ms when skipped does not give 1.25 ms back when moved out: the world's sun
  shadows (map, rough look, contact march) as a half-size pass (the composite's own file, only that block
  compiled in) cost 0.33-0.45 ms and took only 0.6 ms off the composite, net -0.15..-0.27 ms. Read the
  half picture back with the occlusion's upsample: same size `(w + 1) / 2`, so keep its four texels and
  depth weights in globals and reuse them (no second set of depth reads). Even rendered at 640x360 the
  picture stayed equal; characters keep full-size shadows.
- The user playing another instance on the same GPU doubles pass timers mid-run (SSAO 0.5 -> 0.8):
  interleave A/B/A/B and compare within pairs, never across runs.

## TAA motion vectors for skinned characters without touching the game (lesson, Jak 3 Enhanced, Nov 2026)

- No G-buffer attachment and no per-renderer change: replay the skinned draws you already keep for
  the character shadow map (vertex buffers, index ranges, camera-space bones per model) a second time
  after the frame, into an RG16F target cleared to a sentinel (64, 0 = none). Vertex shader skins each
  vertex with this frame's bones AND last frame's bones of the same model; gl_Position from the post's
  own projection with z = 0 (never depth-clipped); the fragment keeps only pixels where its view z is
  within ~3 % of the scene depth (the front surface). TAA: take the offset of the nearest-depth pixel in
  the 3x3 it already scans; elsewhere the camera reprojection as before. 0.09 ms at 2560x1600.
- Finding "the same model last frame" with no stable id from the game: name hash + bone count, nearest
  mean of its bone translations once the camera's move is taken out (view -> previous view), within a
  few meters, one-to-one. Skip non-finite / kilometer-away bone translations (spare bone slots hold
  garbage: the mean went NaN and the Hellcat never matched) and copies of a model with no draws.
- A debug view written by the TAA itself feeds its own history (the TAA output is next frame's input):
  a "how much was clipped" overlay turned the whole screen red by feedback. Keep debug views to masks.
- Proof that works at 640x360: render the test at the window's size and crop a vehicle the camera
  chases right after take-off, A/B toggled by hot tuning ~1 s apart (off: smeared edges; on: crisp).
- **CPU cost of that replay** (measured, Spargus 18h): ~60 models, 360 draws, 0.5 ms of render-thread
  CPU, which was most of a 1 ms "renderer CPU regress". Find such a regress with in-run toggles and a
  per-step CPU profile (no glFinish), each feature off ~12 s in turn with the baseline repeated, and
  read the post's own CPU line, not the total (the total swings +-0.5 ms with other games on the
  machine). Fixes that helped: skip models whose own motion on screen is under ~0.03 px (every bone
  compared with last frame's after the camera's move is taken out, a rotation column's change counted
  at 2 m from the bone), send a model's draws on the same buffers as one glMultiDrawElements, upload
  only the moving models' bones (packed, orphaned), and set `glUniformBlockBinding` and locations once
  per program id. Setting them every frame cost more than the draws themselves. Time each stage
  (match / upload / draws) in the feature's own log line. Traps: animated NPCs and flags really do move
  (only ~7 of 60 models are still), and props whose skeleton count is a placeholder (OpenGOAL's
  merc_replacement gives a joint-less glb `max_bones` 100) carry garbage spare slots that look like
  motion. Bones past the end of the list count as "spare, stop" rather than "moved".
- **Split the post's CPU into named steps before guessing** (a static accumulator, `mark("name")` at
  the top level of each block, sequential index, report every 5 s, only under a profile switch). The
  hot spots were single GL calls, not loops: 48 one-pixel `glReadPixels` into a PBO (exposure) cost
  0.23 ms; one nearest `glBlitFramebuffer` to an 8x6 target at the same pixel centers
  ((2x+1)w/16) plus one read cost 0.06 ms. A `glClear` of the w x h motion target cost 0.13-0.23 ms of
  CPU whatever the clear color, `glClearBufferfv`, or a second target in turn; making the target
  RGBA16F with a frame stamp in b (TAA trusts only this frame's stamp; one clear when the stamp wraps
  at 1024) dropped it with the same coverage. One `glDrawArrays` of a big program (SSAO with SSBOs and
  many samplers) costs ~0.19 ms of driver validation by itself: the next thing to attack.
- **Comparing against an old commit's build**: `git archive <old> | tar -x` into the scratchpad,
  configure Ninja + clang with the cached vcvars env, build `gk` at idle priority (~5 min on this
  laptop), junction the data folders (`out\jak3`, `decompiler_out\jak3_pal`, merc/texture
  replacements, `iso_data\jak3\*`) from the worktree, run with `--proj-path` = the archive. Turn
  the menu's auto quality off in both test configs: an old build without the pre-limiter flush sees
  ~16 ms GPU timers and drops passes, which changes its CPU too. Across separate runs the renderer
  CPU still swings +-0.5 ms with other games' load: only in-run toggles give sub-0.1 ms answers.

## Trees in the wind on a TIE renderer (lesson, Jak 3 Enhanced, Nov 2026)

- **Check the game's own wind moves anything before tuning it**: Jak 3's forest has 697 wind ties (whole small
  trees, bark + foliage) and none moved, even with the bend drawn x20. Prove it with a frame-pair diff (two shots
  0.7 s apart, share of pixels changed > 12) at gain 0 vs 20: identical. Then replace, don't amplify: add your own
  gust as a shear from the instance's foot (`mat[i].x += s * mat[i].y` for the 3 basis rows = x moves by s x height).
- Static TIE (trees baked into world-space vertices) has no instance origin. A per-vertex weight fits in the vertex's
  **padding** (tfrag3 PreloadedVertex had 2 spare bytes after `color_index`, already read by the u16x2 attribute):
  height above the plant's foot + a leaf bit. Foot = a **smooth field** (lowest swaying vertex within ~6 m, bilinear
  between 2 m cell centres): trunk and its leaves then get the same lean and never tear apart.
- Find what is drawn by which renderer before classifying: a weight debug view that also darkens everything with
  weight 0 showed the orange canopies kept their brightness: not static TIE at all, but wind ties. Log each level's
  cutout and wind-draw texture names once (Jak 3: only `fora-foliage`/`fora-bark`; Haven and Spargus have no TIE
  foliage, `wstd-canopy` is a stadium awning: keep "canopy" out of the leaf words).
- Motion has no still-frame proof: report the frame-pair change share (forest top: off 0.3-0.8 %, on 1-2 %) and the
  debug view; the vertex cost was below the GPU-time noise.
## Vanilla A/B in one run, measuring detail, finding what a surface is (lesson, Jak 3 Enhanced, Nov 2026)

- Put a "show the game's own picture" switch in the composite (Jak Enhanced: `tune_raw_view` 1 full, 2 right
  half). Then you can compare against vanilla at the same spot and hour without a second boot. Arena 19h:
  the wall "too dark beside the light column" measured 43-50 vs the game's 61-71, but the far wall was
  46 vs 63 too. The whole room sat at the dusk floor's 0.7x, so it was the deliberate dark look and not
  a local hole.
- Mean luma can't measure a detail term that adds and subtracts. Use the mean |dx| between neighbouring
  pixels (high frequency) or the std over the region. A cavity term on rocky ground: mean 106.2 -> 106.6
  (looked like "no effect"), hf 1.73 -> 2.01 (+17%).
- To find what a surface is, paint the material classes by tag length in the composite (sand 0.9 red, rock
  0.75 green, plain/wall 1.0 blue, the rest grey). Do this before guessing texture names. The desert-start
  "flat slab" turned out to be rocky ground (0.6, wascity-ground-01), not hfrag and not a cave floor. The
  guessed retag changed the material counts but not one pixel there. `JAK_ENHANCED_MATERIAL_NAMES=1` logs
  every texture's class per level. It also turned up wascity-stain-window-01, a streak decal that had been
  tagged as a window pane.
- Haven port 22h from ctyport-start: 0 lamp-tag pixels, ~3 window-pane pixels. The glossy pixels on the
  far quay are marble facades (city-port-green/dark-marble). Lit-window or lamp tags can't light the far
  city from there: that needs another source.
- A shader hot reload that catches a file between two edits fails ("enh_sun_half failed, keeping the old
  one") and recovers at the next save. Wait for the "reloaded" log line after your last edit before you
  shoot. A composite reload at 640x360 took 19-28 s, not 12.
- Far-quay pale band, follow-up: from ctyport-start at 17h it doesn't show (hits reach the quay's foot,
  only a 1-2 px miss line). A wider first-pixel thickness on Hi-Z (one pixel's ray span) moved misses
  within noise (381-411 vs 399-407), so it was dropped. The band depends on the camera spot: record the
  exact spot (teleport) with every water glitch.

## PowerShell pixel scripts: parameters are case-insensitive (trap)

- `param([int]$X)` and a loop `for ($x = $X; ...)` are the same variable: the loop overwrites the
  parameter and never ends (GetPixel out of range, 58 MB of errors in a background task). Name loop
  variables differently, or do pixel statistics in Python + numpy (`python -I`), which also takes
  milliseconds instead of minutes.

## Dense grass by ground class (lesson, Jak 3 Enhanced, Nov 2026)

- Find grassy floor from the level itself: floor textures named grass/moss/lawn/meadow/turf (or green on average and
  not named rock/dirt/path/...), sampled on the **highest tfrag floor** every 2 m. Skip tie triangles there: in a
  forest the tree canopies and rock tops are the highest floor and hide two thirds of the grass (20.7k -> 50.7k m2).
  Then drop spots with anything 0.15-3 m above (rock, roots, ledge), so blades never poke through.
- Cut the grassy area into aligned 64 m squares (one blade field each, the existing zone renderer unchanged), lush
  mask box-blurred ~2 m so edges thin out; hang them on the nearest shrub tree for its time-of-day light. Several
  fields per tree need a list on the tree's field (a holder with n = 0 when the tree has none of its own).
- Colour: never the painted meadow green on a game floor (it read as a green carpet over an autumn forest). A texture's
  mean alone is not the floor's tone either: the same `fora-grass` reads olive in one spot and bright orange in
  another, its tfrag vertex colours are grey (22-38), so the hue difference comes from the post lighting. Per-spot
  colour (texture mean x vertex colour / host light, packed 8+8+8 bits in a float channel, read with texelFetch) plus
  a gain/saturation tune matched the orange spots; keep it behind a switch until the colour comes from the floor as
  drawn. Measure tone with region means of A/B shots (floor 79,51,15 vs blades 60,33,11), not by eye.
- GPU timings from a shared machine (other test instances) swing 6-15 ms between identical variants: interleave
  off/on several times and report ranges, or use per-pass timers.
