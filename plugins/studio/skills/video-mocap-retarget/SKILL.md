---
name: video-mocap-retarget
description: Video to 3D motion capture on a local Windows GPU (NVIDIA GEM-X / SOMA body model) and retargeting the result onto a game character rig in Blender headless - Windows install pitfalls, trimming screen recordings, camera/world frames, why a seated or partly hidden subject needs yaw alignment to the camera instead of pelvis normalisation, duplicated frames in screen recordings, zero-phase filtering with acceptance numbers, analytic contacts (sill, wheel, lap, mouth) baked to FK, hand-keyed fingers, a render camera rebuilt from the mocap camera. Use when turning a reference clip into an animation for a rig.
---

# Video mocap -> retarget (GEM-X + Blender)

Lessons from a meme shot: a man seated in a pickup, seen through the driver window, handheld phone video
recorded from a screen, retargeted onto a Jak-like 64-bone rig (Jak Enhanced, 2026-11).

## Install on Windows (GEM-X, NVlabs)

- Pure Python, no custom CUDA ops. Python 3.12 venv with `uv`; RTX 50xx (sm_120) needs cu128+ wheels
  (torch 2.11.0+cu128 works). Weights: `nvidia/GEM-X` (~7 GB: body ckpt 3.5 GB + ViTPose 3.4 GB + motion),
  SOMA assets `nvidia/SOMA-X` revision `v0.3.3` (not gated). Check sha256 against the HF API `lfs.oid`.
- Big downloads on a busy machine: `uv` can panic with Windows error 1450 and curl can fail with
  "Failure writing output" (code 23). Download wheels and weights with `curl -L -C - --retry` in a retry
  loop, then `uv pip install <wheel files> -e repo[video]` with `UV_LINK_MODE=copy` (the venv then
  survives deleting the uv cache and the wheels: ~7.7 GB back).
- The person detector the docs ask for (YOLOX-HumanArt) comes from download.openmmlab.com. If only
  NVIDIA/PyPI/pytorch.org sources are allowed, monkeypatch `gem.inference.body_video.YOLOXONNX` with a
  torchvision Faster R-CNN v2 wrapper (`detect(bgr) -> boxes xyxy, scores`, person label 1) in a small
  launcher script; the repo stays untouched.
- `gem-render` needs Linux/EGL: draw your own overlay by projecting the in-camera joints with `K`.
- 412 frames (13.7 s, 1774x920) took ~7.5 min and ~7 GB VRAM peak on an 8 GB laptop GPU.
- Output: `pred_soma_params_incam/global` (axis-angle, 76 body joints + root). Run the official
  `SomaFixedGs1BodyAdapter(..., return_joints_only=True)`: `transforms` has **78** entries
  (`Root` + 77 public joints; names = runtime `public_joint_names`, parents = `public_joint_parent_ids`,
  Root points to itself), `joints` has 77 (no Root). SOMA axes: +Y up, +Z forward, +X = subject's left, m.
- The SOMA `Jaw` joint barely moves (1-3 deg): useless for lip sync, use the audio envelope.
  Body-model fingers are almost static (5-10 deg std): hand-key finger poses instead.

## Clip preparation

- Screen recordings of a player: find the first clean frame after the scrub/fade and the last before the
  end card by tiling exact frame numbers (`select='between(n,30,39)'`, `tile`); crop away the player bar.
  Write the trim down in source frames and keep the scene timeline offset (here scene f = clip f-2).
- Screen recordings duplicate ~1/3 of the frames: `tblend=all_mode=difference,signalstats` YAVG is
  bimodal (duplicates < 0.1). Replace the poses of duplicated frames with slerp between unique
  neighbours, otherwise you get 20-30 deg/frame "jitter" that is really stair-stepping.

## Retarget of seated / partly hidden subjects (main lesson)

- **Align yaw to the camera, do not normalise the pelvis.** GEM-X puts the whole torso yaw in the root.
  Turning the mean pelvis to face forward (or removing per-frame pelvis motion) rotated the torso of a
  man turned 25 deg toward his window, so the arm resting on the sill ended up folded on the chest
  (looked like monocular depth error, was a retarget bug). Instead: Kabsch `cam_pos -> glob_pos` per
  frame gives the GEM-X camera in world (residual ~1e-6); rotate the world about Z only so the GEM-X
  camera azimuth matches the shot camera azimuth (circular mean of the difference; std was 3.6 deg).
  Keep GEM-X gravity (an extra "level the chest" correction was wrong).
- Keep the character's pelvis bone constant (seat), feet on their existing IK; put half of the pelvis
  delta into the lower spine (slerp pelvis/spine 0.5) and full deltas on chest/neck/head/arms.
- Per bone: `target_arm_space = D(t) @ C^-1 @ W_rest`, `D = R_soma(t) R_soma_rest^T` (both in the same
  frame), `C` = minimal rotation from the SOMA rest bone direction to the rig rest bone direction. Local
  basis = `Rrel^-1 @ Rparent_pose^-1 @ target`, in hierarchy order; write FK quaternion keys.
- A clavicle following ~40% of the arm elevation keeps a shoulder pad from crumpling on raised arms.

## Filtering with numbers

- Zero-phase one-euro on local quaternions (forward + backward pass, sign-aligned, nlerp of the two).
  Acceptance per bone: rest jitter < 0.25 deg/frame (calmest quarter of the clip), gesture peaks >= 90%
  of raw (30-frame window ranges), lag 0 (cross-correlation). Gesture beats had a ~9 frame period, so a
  5-7 frame box filter or a 1.2 Hz cutoff on the spine killed them: raise the cutoff per bone until the
  peak test passes (spine ended at 6 Hz, head 1.2-1.5 Hz, arms 2.5-4 Hz, hands 1.5-6 Hz).

## Contacts (analytic, then bake)

- Two-bone IK in numpy with swing-only corrections (keep the mocap twist; keep the hand's armature
  orientation so the wrist does not inherit the change). Remove blockout IK constraints, bake FK keys.
- Sill: find where shoulder->elbow->wrist crosses the sill plane; clearance = z - (top + forearm radius
  from the mesh); weight 1 below, smoothstep to 0 at +6 cm; smooth the offset but never below the
  penetration. Wheel: attractor with hysteresis (on < 10 cm, off > 20 cm, weight smoothed 9 frames).
  Lap: minimum height and distance from the torso axis. Mouth: use the hand tip (not the wrist) within
  30 cm of a mouth point taken from the head mesh.
- Report: penetration before/after, frames on the wheel, max wrist distance while locked, drift of the
  pelvis and ankles, max deg/frame with the frame number.

## Camera

- For a 1:1 read build a camera from the GEM-X camera: rotation `Rz(psi) M Rcw diag(1,-1,-1)`, position
  = chest + s * (camera - chest) rotated the same way, `s = lens / (35 mm equivalent of the GEM-X focal)`
  (focal 1998 px on a 1774 px width ~ 40.5 mm), 1 Hz zero-phase low-pass, in world (not parented to a
  bobbing vehicle). Leave the user's cameras untouched; make the new one active only in the copy.
