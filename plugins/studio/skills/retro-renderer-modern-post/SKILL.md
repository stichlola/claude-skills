---
name: retro-renderer-modern-post
description: Adding modern rendering effects to an old-console game's PC renderer (OpenGOAL Jak 3 here, OpenGL) without touching its assets - one post pass between the 3D buckets and the HUD, view-space positions rebuilt from the game's own projection, then TAA by wrapping the world shaders' main() with a per-frame jitter, volumetric mist marched in view space, screen-space sun shadows, SSAO/SSGI, bloom, god rays, water reflections; plus how to test sun-dependent effects and what screen space cannot do. Use when the user wants "next-gen" or remaster-style graphics in a decompiled/ported game's renderer, or asks for TAA, volumetrics, AO or similar in such a renderer.
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
  soft darkening; crisp shafts in alleys need a real sun shadow map. Keep the visibility test in
  one function so a shadow map can replace it.
- **Energy**: forward scattering toward the sun blows out quickly; cap the sun term and start
  subtle (density ~0.004/m, falloff ~4 m). Water and low ground far below the camera are inside the
  densest layer - judge the defaults on a view over water.

## Testing light-dependent effects

- The key light the game hands over is not the sun disc in the sky texture; log its view-space
  direction before judging shafts or shadows.
- Add a test switch that **turns the sun around the up axis** (`JAK_ENHANCED_SUN_YAW`), not one
  that negates it (that puts it under the horizon and every sun effect switches off). Log the
  view-space sun for a few yaws, pick the one in front of the review camera.
- Exaggerate first (10x density, 3-5x sun) to see the structure, then tune down.

## What screen space can't do

Off-screen occluders, light from behind the camera, anything hidden behind the foreground. The
next real steps are geometry-side: normals computed at extraction (dynamic lights), sun shadow
maps (every renderer drawn again from the sun), then ray tracing (compute-shader BVH, or Vulkan).
