---
name: threejs-performance
description: Proven fixes for slow or ugly three.js scenes in web games - first-seconds lag, shader recompiles on every edit, adaptive quality that made phones blurry, instancing, render on demand, shadows lost when zooming, coalesced 2D canvas redraws, background thumbnail renderers, and how to measure before and after. Use when a three.js/WebGL scene stutters, lags while editing or panning, looks pixelated or loses shadows, or before adding heavy effects.
---

# three.js performance: what fixed real lag

From a top-down 3D board game (React + three.js r18x, phones and desktops). Measure first, change
one thing, measure again, and look at screenshots: a "faster" change that looks worse is a regression.

## Measure

- Expose a debug handle (`?debug=1` → `window.game`, `window.stats`): frame time, draw calls
  (`renderer.info.render.calls`), triangles, programs (`renderer.info.programs.length`), and how long each
  rebuild took. A growing program count while editing = shaders recompiling (see below).
- Benchmark script with Playwright (headless Chromium + SwiftShader, see the cloud-agent-workflow skill)
  that loads a fixed scene and records frame times; give it a threshold so regressions fail.

## The fixes, by symptom

**Lag in the first ~15 s** (models loading, shaders compiling, quality settling)
- A tiny "warm-up gate": `holdHeavyWork(ms)` pushes a deadline, `await afterWarmUp()` waits for it.
  Anything that can wait (palette thumbnails, previews, prefetch) awaits it; pointer-down and pan also
  call `holdHeavyWork(1500)` so background work never competes with the hand.
- Adaptive quality must **skip the warm-up frames** and ignore single huge frames only above ~1 s (tab
  switches), not above 250 ms, or it never sees the real cost.

**Lag on every edit (placing objects, painting)**: shader programs recompiled
- Cause 1: the old meshes' materials were disposed *before* the rebuilt scene was rendered, so three.js
  dropped the program and compiled it again. Fix: **retire, render, then release** - push old objects to
  a `retired` list, dispose them only after the next `composer.render()`.
- Cause 2: materials shared from a cache (e.g. wind-animated foliage) were disposed with the mesh. Mark
  them `material.userData.shared = true` and skip them in dispose.
- Throttle rebuilds (e.g. at most one board rebuild per 350 ms while a stroke is under way) and rebuild
  incrementally where you can (only the changed chunk of ground).

**Many copies of the same model**: `InstancedMesh` per (geometry, material); one draw call for a forest.
Keep per-instance bounding spheres for culling.

**Idle cost**: render on demand - only when the camera, the scene or an animation changed; animated
things (water, wind, fire) request frames while visible.

**Blurry/pixelated on phones after "optimising"**: adaptive pixel ratio dropped to 0.6. Put a **quality
floor** (e.g. phones never below level 2 of 5, desktops never below 3) and **drop the expensive effects
first** (SSAO, bloom, DOF, shadow-map size), resolution last. When you change the quality model, bump
the stored key (`quality3d.3`) so old saved low settings don't stick.

**Shadows disappear when zooming in**: shadow-only proxy meshes on a separate layer. three.js's shadow
pass tests casters against the *main camera's* layers, so with that layer disabled on the camera they
threw no shadow. Fix: let the sun see the layer while the shadow map renders:

```ts
export function sunSeesShadowLayer(renderer: THREE.WebGLRenderer) {
  const map = renderer.shadowMap as THREE.WebGLShadowMap & { render: (l: THREE.Light[], s: THREE.Object3D, c: THREE.Camera) => void };
  const render = map.render.bind(map);
  map.render = (lights, scene, camera) => {
    const had = camera.layers.isEnabled(SHADOW_LAYER);
    camera.layers.enable(SHADOW_LAYER);
    try { render(lights, scene, camera); } finally { if (!had) camera.layers.disable(SHADOW_LAYER); }
  };
}
```
Also fit the shadow camera to what is on screen, and keep its texel size stable while zooming.

**Thumbnail/preview renderers slowing the editor**: an extra WebGLRenderer + `toDataURL` per thumbnail
blocks the main thread. Render them after warm-up, one per idle slice, cache the data URLs (bump a
version key when models change).

**2D canvas panning feels sticky**: coalesce redraws with requestAnimationFrame (`drawSoon()` sets a
flag; one draw per frame), cache static layers in offscreen canvases, redraw only the moving layer.

**Gestures**: on touch, one finger paints; press-and-hold (~350 ms) or two fingers pans. Show a hint
once, with "don't show again".

## Assets

- GLB with meshopt + quantisation (`gltfpack -cc -kn -km -ke -vp 12`), WebP textures, one atlas and one
  material per kit; register `MeshoptDecoder` on the GLTFLoader.
- Ask the generator for the right face count up front (see the tripo-3d-assets skill); never decimate
  generated meshes.
- Shadow casters: cheap proxies (boxes/low LOD) on the shadow layer; the detailed mesh doesn't cast.

## Checklist before declaring it faster

1. Same scene, same device class, before/after numbers (frame time p50/p95, draw calls, programs).
2. Programs stay constant while editing.
3. Screenshot comparison at the zooms the user uses (close, mid, far) - shadows, crispness, colours.
4. Phones: first 15 s smooth, no blurry floor.
