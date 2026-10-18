# Animating creatures with unusual bodies (from generated video)

For bipeds, clips written in code onto a shared skeleton are enough (QuestBoard's `tools/tripo/rig.py`: one set
of world-space poses turned into each model's bone rotations). People also have motion capture and
Mixamo-like libraries. Quadrupeds, dragons, wings, tails and monsters have no such data. This is the route
that worked in a published experiment (Tripo model → generated video → skeleton). It has not been tried in
QuestBoard yet.

## The pipeline

1. **Model** from Tripo (as in SKILL.md).
2. **Skeleton** with UniRig (an AI that puts bones inside a mesh). Make several tries and score each one
   against the mesh:
   - every leg that touches the ground has a bone chain;
   - left and right match;
   - the best try is kept.

   Then fold the fingers into the hand and cut off bones that stick out of the body. Single tries came back
   with bones outside the mesh, or with no legs at all.
3. **Video with two cameras in one picture.** Ask the video model (Seedance was used) for a single frame
   holding a front view and a side view of the creature side by side. Two separate videos never match,
   because every generation differs even with the same input. With two views, each joint's 3D position is
   where the two sight lines cross: simple triangulation, no depth guessing.
4. **Check the clip before using it.** Do both halves show the same movement? Sometimes the two views act
   differently. Then make a new video: that is cheaper than repairing it.
5. **A joint detector trained on this one creature.** No pose model has seen your monster, but you own it:
   - render about 3000 random poses from the same two cameras, each joint bent at random within real joint
     limits, about half of them fast so arms and legs are motion-blurred;
   - make the pictures a bit worse, the way generated video is: light, colour shifts, blur;
   - fine-tune DINO (Meta) to find every joint. The truth is free: you made the renders.

   About 30 minutes on one consumer GPU, **once per creature**. After that, reading a clip takes seconds.
6. **Triangulate, put the motion on the skeleton**, export to Blender and the engine.

## The exam (test before paying for videos)

For every creature, even a brand new one, invent a motion yourself:
- random joint motion within the limits;
- filmed with the same two cameras;
- run through the tool like any generated clip;
- compared with the known motion, bone by bone.

The tool must pass before any paid video is made, and again after every change to the tool. This replaced
an agent checking every frame by hand: about four days and many tokens per troll before, minutes after.

## What failed (don't retry)

- **Keyframes written by an agent** (a deer walk): blocky, not animal-like, even on a better mesh.
- **Fitting the silhouette per frame from one video**:
  - from the side the legs cross and the fit loses which leg is which, so the feet had to be marked by hand;
  - depth from a single view is a guess and comes out wrong.
- **Point tracking** (DeepMind): seeded from a known first frame, but after a few steps the points slide off
  the legs onto the body.
- **SAM 2 outlines** per leg: fine on a walk; on a run the legs blur, the far legs vanish or jump onto the
  chest, and the back leg takes the front leg's label.
- **Depth Anything** (depth from one picture): near and far legs are about 10 cm apart, too close for it;
  right 4 times out of 10.
  - A depth model trained on your own renders picked the nearer leg every time. With two cameras it added
    almost nothing, and it cannot replace the second camera: it knows which leg is nearer, not how far.
- **Painted legs** (each leg its own colour): it worked, but only while the video model keeps the colours,
  which is not guaranteed. It also does not scale to 6 limbs, wings and so on.
- **Animal pose detectors**: from the side they draw the far legs on the belly; from the front, a mess.
- **MoCapAnything** (trained on real animal motion capture): the wolf ran in place, the gallop was off, and
  it does not cover monsters.

## Limits that remain

- If the two views show different motions, the tool can follow only one: regenerate.
- A hand hidden behind the body is still a guess.
