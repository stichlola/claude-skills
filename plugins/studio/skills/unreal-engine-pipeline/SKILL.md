---
name: unreal-engine-pipeline
description: Unreal Engine 5 (5.8) asset pipeline and runtime pitfalls met building a game from code and Python only - headless imports with Interchange, master materials built in Python, Nanite limits (64 sections, masked sections, quantisation of huge meshes, pool size), instanced meshes going grey, virtual shadow map costs, additive glows turning white, GC crashes from raw UObject pointers, sounds/music, measuring fps, and running editor commandlets reliably on Windows. Use when importing assets into Unreal from scripts, writing UE C++ gameplay/rendering code, or debugging crashes, grey materials, broken meshes or low frame rates in an Unreal project.
---

# Unreal Engine 5 pipeline: pitfalls and fixes

From jak3-ue5 (a PS2 game rebuilt in UE 5.8 without the editor UI: C++ game code, a Python import
script, an empty map filled at runtime). Each line cost a debugging session.

## Headless import (Python)

- Run: `UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<ABSOLUTE path> -unattended
  [-abslog=<file>]`. A relative `-script` path is resolved against the process's working directory
  and fails as `NameError: name 'Jak3' is not defined`.
- glb via `InterchangeGenericAssetsPipeline`; `combine_static_meshes_behavior = ALL` turns a level's
  nodes into one mesh, `NONE` keeps pieces apart; `force_all_mesh_as_type` for static/skeletal.
- Master materials built in Python (`MaterialEditingLibrary`): re-create by emptying an existing master
  (`delete_all_material_expressions`) so instances stay attached. `MP_DISPLACEMENT` is not exposed to
  Python (needs a tiny C++ editor helper). `TextureSample` takes a `TextureObjectParameter` in "Tex"
  so one texture feeds several samples (detail at ×N UVs, bump via `NormalFromHeightmap`).
- **A material used on instanced meshes needs `used_with_instanced_static_meshes = True`**, or the
  engine silently draws its grey default material on every instance.
- Give texture-only detail to low-res game textures in the material: the same texture at ×4-6 UVs as a
  luminance ratio (fine / base, clamped 0.5-1.5) and a second fine bump; per-level strength parameters.
- Wind sway = World Position Offset: sin(time·speed + world-position phase) + a faster flutter, times
  saturate(LocalPosition.z / height), along one wind direction, scaled by a per-instance-set strength.

## Nanite

- No Nanite mesh with **more than 64 material sections** ("Unsupported number of sections"): split the
  glb by material into parts.
- With tessellation/displacement on, Nanite **dropped masked (see-through) sections**: import foliage
  cards as a separate non-Nanite mesh.
- On a **mesh 2 km across Nanite quantises positions, normals and UVs**: thin props break apart, rocks
  go faceted, textures smear into streaks. Precision settings did not fix it; import such levels
  without Nanite. Small props are fine with Nanite.
- **Displacement vs decals**: games lay decals (stains, cracks, bullet holes) flat on floors; a
  tessellated, displaced floor pokes through them in squares that change with the view distance. Turn
  displacement off (per material instance) on levels with decals; keep it for rock and cliffs.
- Materials used on Nanite meshes need `used_with_nanite` (and `used_with_instanced_static_meshes` for
  HISM props), else "missing usage flag Nanite! Default Material will be used" and they draw grey.
- What Nanite buys on low-poly (PS2) worlds is not triangle count: it is virtual shadow map cost (many
  non-Nanite meshes overflow the "Non-Nanite Marking Job Queue"), tessellation, and dense instanced
  props (AI-generated models). Keep huge meshes and see-through foliage off it.
- `r.Nanite.Streaming.StreamingPoolSize` must stay **below 2048 MB** (fatal error otherwise); 1536 works
  on an 8 GB laptop GPU.

## Rendering costs and looks

- Log "[VSM] Non-Nanite Marking Job Queue overflow": many non-Nanite meshes over the shadow map. Make
  instanced props Nanite, turn off cast shadows on small grass, and on far/hazy plain meshes.
- Swaying foliage (WPO) re-renders its virtual shadow pages every frame: set
  `WorldPositionOffsetDisableDistance` (~50 m) and `ShadowCacheInvalidationBehavior = Static`.
- Measure, don't guess: log average fps over a scripted run and toggle one feature at a time (the
  first run after an import is slower: shaders compile). Here: dust storm −5 fps, 1162 foliage
  instances −1, plain 2 km levels most of the rest.
- **Additive glow saturates to white**: a pale colour × intensity 40 tonemaps to white. Use a deep,
  saturated colour (e.g. red 1, 0.015, 0.01) and a lower intensity (~12); same for thruster flames.
- A Fresnel-faded (1−Fresnel) material vanishes on flat shapes seen edge-on (ground shock waves): use
  a plain additive glow there.
- "Texture streaming pool over budget" can simply mean **two game instances** are open at once on the
  same GPU; check `ListTextures` totals before shrinking textures (here 240 MB of a 3000 MB pool).

## C++ runtime

- **Never keep `UObject*` (animation sequences, sounds...) in plain structs or non-UPROPERTY maps.**
  An `UAnimSequence` held only by a `TMap` without `UPROPERTY` (or a nested enum key UPROPERTY can't
  take) was garbage-collected: the first time a death clip played, the game crashed in
  `NativeUpdateAnimation` (`Index >= 0` in UObjectArray / access violation at 0x0). Hold them in a
  `UPROPERTY TArray<TObjectPtr<...>>` alongside, or make the struct a `USTRUCT` with `UPROPERTY`
  members.
- UHT cannot see a `using` alias: a `UPROPERTY` must name the `USTRUCT` type itself.
- Music: two `UAudioComponent`s cross-fading (`FadeOut` / `FadeIn`), `bIsUISound = true` so it is not
  positional; loops flagged `looping` on the SoundWave at import.
- `FParse::Value` stops at commas unless `bShouldStopOnSeparator = false` (comma lists on the command
  line). For a repeated `-Flag=` the first occurrence wins: append defaults after the user's arguments.
- Build with `Build.bat <Proj>Editor Win64 Development -Project=... -WaitMutex -NoHotReload
  -NoHotReloadFromIDE`; it fails with LNK1104 while a game or commandlet of the project still runs
  (DLL locked).

## Windows automation (agents)

- A commandlet started from a background shell may outlive it or die with it: start it detached
  (`Start-Process ... -PassThru`) and wait on its process (`WaitForExit` / `Wait-Process -Id`).
  `tasklist | grep` loops in a monitor gave false "finished" events; logs read later may still be from
  an older run, so compare timestamps.
- Never run two imports at once: they write the same packages.
- Test-driving from the command line beats guessing: a `-Start=<place>` and a timed teleport option plus
  timed screenshots reproduce "it looks wrong when I get there" reports (it showed the problem was the
  spawn point and the decals, not streaming).
- `FParse::Value` stops at commas by default: pass `bShouldStopOnSeparator = false` for lists.
- On Windows the agent's PowerShell may not see the user's Python (only the Store alias): call it by
  full path or prepend its folder to PATH before launching scripts that call `python`.
- `Remove-Item` on a variable path built next to "C:\Program Files" was blocked by the sandbox: write to
  a fresh folder instead of deleting.
- Bash heredocs with `\0` or `'''` content corrupt Python sources (a literal NUL byte): write patch
  scripts to a file, or use `bytes(n)` instead of `b"\0" * n`.
