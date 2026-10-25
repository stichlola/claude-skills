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
- Characters aren't in the map: keep the screen-space sun shadows on for them.
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
