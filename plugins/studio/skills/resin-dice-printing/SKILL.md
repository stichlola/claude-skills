---
name: resin-dice-printing
description: Methodology to model, support, print and finish polyhedral dice on an MSLA resin printer so edges stay sharp and faces flat - design rules for the STL (engraving depth, sharp vs bevelled edges, number islands, solid not hollow), vertex-down orientation with "fin" supports along the lower edges, print/wash/cure settings, then two finishing routes - opaque painted dice (filler primer, number fill flush, sealing) and translucent/clear dice (wet sanding ladder 800 -> 12000, plastic polish or clear dip coat, yellowing control) - plus masters for silicone moulds. Use for any D4-D20 set, custom/engraved dice, dice orders for clients, and when writing print instructions to send with dice STLs.
---

# Resin dice: model, print, finish

Sources: Hoffman Engineering and Rybonator videos (fin supports after Rev Chumley / Imagination Labs),
plus shop practice. Pairs with `blender-engraved-dice` (building the die) and `mesh-hygiene` (export).

## 1. Model rules (Blender)

- **Engraving depth >= 1.0 mm** (1.2 mm on d20/d4 small faces is fine). 0.5 mm disappears when the
  faces are sanded. Width of strokes >= 0.6 mm or the paint will not go in / resin will not clear out.
- **Solid, not hollow**, uniform material: a die must roll fair. Never add drain holes.
- **Edges**: sharp-edged dice need fins (section 2) or they print rounded. A small bevel (0.3-0.5 mm)
  is more forgiving and hides support marks; decide per client and say which in the brief.
- **Number islands** (0, 4, 6, 8, 9, A, B...): the inner island is a separate overhang when that face
  points down; orient so those faces point up/sideways.
- **Sizes** of a standard set: d4 ~20, d6 16, d8 ~20, d10 ~16x20, d12 ~18-19, d20 ~20-21 mm.
- Export: hygiene report (0 non-manifold, 0 fragments), one STL per die, plus a pre-supported STL if
  the client prints it himself. Generator for plain fonts: dicemaker.net.

## 2. Orientation and supports (Chitubox / Lychee)

- **Stand the die on one vertex**, straight up (rotate around the lowest vertex until no face leans).
  No face on the plate and no face resting on supports: the plate texture or support pits end up on
  a face and every face must be finished the same way.
- **Fin supports**: light supports, **contact 0.2 mm**, placed **touching each other** along every
  edge that leaves the bottom vertex (and on the lowest ring of edges on d12/d20). They form a solid
  wall that forces straight edges - this is what removes droopy/rounded corners on budget printers.
- Put the fin **just beside the edge, not on it**, and never over a vertex: cutting it off then
  chips nothing. Angled supports pointing at the edge work better than straight-down ones.
- A heavier support under the bottom vertex; a light support on number islands that overhang.
- Support even the d6 - do not print it flat on the plate.

## 3. Print and post-process

- Layer 0.05 mm, normal exposure for the resin (+~2 s for cheap resins vs premium ones).
- Wash 5 min in IPA 91%+ (or resin cleaner), dry fully.
- Cut fins with flush cutters lying flat on the face; pull the island supports.
- Cure: **opaque** 5-10 min; **clear** short cure (2-3 min, or under water) - over-curing yellows it.

## 4a. Opaque dice (painted, primer)

1. Sand support ridges and layer lines: 400 -> 600 -> 800 wet, **one direction per face** (circles
   round the edges). Use a flat block or glass with the paper on it to keep faces flat.
2. **Filler primer** (spray, thin coats), let dry, wet sand 800 -> 1000 so faces are smooth.
3. Base colour by airbrush/spray; optional gloss coat before step 4 so the fill wipes off cleanly.
4. **Fill the numbers**: acrylic/enamel or paint pen into the engraving, wait a minute, wipe the face
   flat with a barely damp cloth/card (enamel: thinner) so paint stays only in the recess.
5. **Seal**: 2-3 thin coats of gloss or satin varnish (2K/UV varnish lasts best for rolling dice).

## 4b. Translucent / clear dice

1. Clear resin, short cure (section 3). Remove supports.
2. **Wet sanding ladder**, ~20 strokes per face per grit, one direction, on a flat backing:
   800 -> 1500 -> 2000 paper, then Micro-Mesh 2400, 3200, 3600, 4000, 6000, 8000, 12000.
   Faces look worse (frosted) until the last grits - normal. About 1 h per set by hand; a turntable /
   pottery wheel with paper (Zona papers) speeds it up.
3. **Polish** with plastic polish (Meguiar's PlastX or similar) and a microfibre cloth.
   Shortcut instead of the full ladder: sand to 1500 then **dip/brush a thin coat of the same clear
   resin** (or spray clear 2K gloss) and cure - glassy at once.
4. Fill numbers last (opaque paint or pigmented resin, wipe flush, re-polish the face).
5. Expect visible micro-bubbles inside: degas or warm the resin, print slower lifts.

## 4c. Acrylic number fill (shop default) and UV gloss resin

- Seal the surface **before** filling (varnish or a thin UV gloss resin coat): on bare sanded resin
  acrylic stains the sanding scratches around the numbers.
- Fill with slightly thick acrylic, wait ~1 min, wipe the face with a barely damp sponge/cloth over a
  flat card; second pass if it shrinks. Let it dry fully (hours) before the top coat.
- Acrylic is not durable on a rolling die: always top-coat (varnish, or thin UV resin on faces only -
  resin pooling on edges rounds them and unbalances the die).
- Clear dice with UV gloss resin: sand to 1500, thin UV resin coat (replaces 2000-12000 + polish),
  acrylic fill, final thin UV resin/varnish. Use the shop's existing varnish/resin before buying.

## 5. Masters for silicone moulds (cast dice)

- Printed resin is softer than casting resin and scratches; for real use, cast from a mould.
- SLA resin **inhibits platinum silicone**: coat (Inhibit X or clear gloss) or let the master air out
  for weeks, and test on a scrap first. Sand masters to 2000+ before moulding: every scratch is cast.

## Checklist to give the client / user

engraving >= 1 mm - vertex down - fins 0.2 mm touching, beside the edges - 0.05 mm layers -
short cure if clear - sand one direction on a flat block - opaque: filler primer, fill, varnish -
clear: ladder to 12000 + polish (or dip coat).
