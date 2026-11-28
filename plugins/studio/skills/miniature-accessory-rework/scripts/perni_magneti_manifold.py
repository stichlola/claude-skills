# Karna v4: magnet pockets 8x3 (2 per joint) + ribbed press-fit pins. manifold3d + trimesh, mm.
import json, time, numpy as np, trimesh, manifold3d as m3, math, shutil, os
V3 = r"C:/Users/david/Documents/my music minis/adi silverman/karna_pezzi_v3/"
V4 = r"C:/Users/david/Documents/my music minis/adi silverman/karna_pezzi_v4/"
MAG_R, MAG_H = 8.2/2, 3.2      # pocket for 8x3 magnet: dia 8.2, depth 3.2 (magnet sits 0.2 below the face)
WALL = 1.2; PIN_KEEP = 2.62 + MAG_R + 1.5; MIN_SEP = 12.0
def M(tm): return m3.Manifold(m3.Mesh(vert_properties=np.asarray(tm.vertices, np.float32), tri_verts=np.asarray(tm.faces, np.uint32)))
def T(man):
    mm = man.to_mesh(); return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=False)
def rot_to(n):
    n = np.asarray(n, float); n /= np.linalg.norm(n); z = np.array([0, 0, 1.])
    v = np.cross(z, n); s = np.linalg.norm(v); c = z @ n
    if s < 1e-9: return np.eye(3) if c > 0 else np.diag([1, -1, -1])
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]); return np.eye(3) + K + K @ K * ((1 - c) / s**2)
def cyl(p0, n, r, h, seg=64):
    R = rot_to(n); return m3.Manifold.cylinder(h, r, r, seg).transform(np.hstack([R, np.asarray(p0, float).reshape(3, 1)]).tolist())
t0 = time.time()
tms = {k: trimesh.load(V3 + f"Karna_{k}.stl") for k in ["Base", "Drago", "Testa"]}
P = {k: M(v) for k, v in tms.items()}
info = json.load(open(V3 + "karna_v3_taglio.json", encoding="utf8"))
pins = info["perni"]
JOINTS = [("Base", "Drago", np.array(pins[0]["n"])), ("Drago", "Testa", np.array(pins[3]["n"]))]
rep = {"magneti": []}
rng = np.random.default_rng(1)
for lo, hi, d in JOINTS:
    d = d / np.linalg.norm(d); tm = tms[hi]
    fn = tm.face_normals; cand = tm.triangles_center[(fn @ d) < -0.97]
    # keep only points where the lo piece is right below (interface faces)
    from scipy.spatial import cKDTree; q = cKDTree(tms[lo].vertices)
    cand = cand[rng.choice(len(cand), min(3000, len(cand)), replace=False)]
    dist = q.query(cand)[0]; cand = cand[dist < 0.4]
    jp = [np.array(p["c"]) for p in pins if p["hi"] == "Karna_" + hi and p["lo"] == "Karna_" + lo]
    def perp(a, b): w = a - b; return np.linalg.norm(w - (w @ d) * d)
    cand = [c for c in cand if all(perp(c, p) > PIN_KEEP for p in jp)]
    cand = [cand[i] for i in rng.permutation(len(cand))[:250]]
    if hi == "Testa":   # flat neck cut: sample a grid on the cut plane instead of face centres
        P0 = np.array([0.5, -46.6, 100.4]); Cc = np.array([1.2, -21.9, 110.7]); Cc = Cc - ((Cc - P0) @ d) * d
        Rm = rot_to(d); g = [Cc + a * Rm[:, 0] + b * Rm[:, 1] for a in np.arange(-21, 21.1, 1.5) for b in np.arange(-21, 21.1, 1.5)]
        cand = [c for c in g if all(perp(c, p) > PIN_KEEP for p in jp)]
    W = P[lo] + P[hi]; good = []; errs = []
    print('candidati prima del test', len(cand))
    for S in cand:
        sh_hi = cyl(S + 0.5 * d, d, MAG_R + WALL, MAG_H - 0.5 + WALL)
        sh_lo = cyl(S - (MAG_H + WALL) * d, d, MAG_R + WALL, MAG_H - 0.5 + WALL)
        e = ((sh_hi + sh_lo) - W).volume()
        errs.append(e)
        if e < 0.3: good.append(S)
    print('errori min/quartili', np.round(np.percentile(errs,[0,10,25,50]),2) if errs else None)
    print(lo, hi, "candidati validi", len(good), round(time.time() - t0, 1), "s")
    if len(good) < 2: raise SystemExit(f"STOP: meno di 2 posizioni per magneti tra {lo} e {hi}")
    # pick the pair farthest apart, then prefer near the section centre among near-ties
    G = np.array(good); best = None
    for i in range(len(G)):
        for j in range(i + 1, len(G)):
            s = perp(G[i], G[j])
            if s >= MIN_SEP and (best is None or s > best[0]): best = (s, i, j)
    if best is None: raise SystemExit("STOP: magneti troppo vicini")
    for k in (best[1], best[2]):
        S = G[k]
        P[hi] = P[hi] - cyl(S - 1.5 * d, d, MAG_R, MAG_H + 1.5)
        P[lo] = P[lo] - cyl(S - MAG_H * d, d, MAG_R, MAG_H + 1.5)
        rep["magneti"].append({"giunto": f"{lo}-{hi}", "centro_faccia": [round(float(x), 2) for x in S], "asse": [round(float(x), 4) for x in d]})
    print("  distanza tra i magneti", round(best[0], 1), "mm")
# ribbed pins
def pin(dn, L, hole_r):
    r = dn / 2; R = hole_r + 0.10; ch = 0.4
    prof = [(0, 0), (r - ch, 0), (r, ch), (r, 1.5), (R, 3.0), (R, L - 3.0), (r, L - 1.5), (r, L - ch), (r - ch, L), (0, L)]
    env = m3.Manifold.revolve(m3.CrossSection([[(x, y) for x, y in prof]]), 96)
    core = m3.Manifold.cylinder(L, r, r, 96)
    ribs = m3.Manifold()
    for a in (0, 120, 240):
        b = m3.Manifold.cube([R + 0.2 - (r - 0.3), 0.6, L]).translate([r - 0.3, -0.3, 0]).rotate([0, 0, a]); ribs = ribs + b
    return (core + ribs) ^ env
kinds = [(5, 14, 6), (4, 12, 3), (3, 10, 4)]
allp = m3.Manifold(); x = 0
for dn, L, cnt in kinds:
    for i in range(cnt):
        allp = allp + pin(dn, L, dn / 2 + 0.12).translate([x, 0, 0]); x += dn + 4
os.makedirs(V4, exist_ok=True)
out = {}
for k in P:
    tm = T(P[k]); comps = tm.split(only_watertight=False)
    big = max(comps, key=lambda c: abs(c.volume)); tm = big
    deg = int((tm.area_faces < 1e-10).sum())
    out[k] = {"vol_cm3": round(tm.volume / 1000, 3), "watertight": bool(tm.is_watertight), "isole": len(comps), "degeneri": deg, "facce": len(tm.faces)}
    tm.export(V4 + f"Karna_{k}.stl")
tp = T(allp); tp.export(V4 + "Karna_Perni_alette_6xD5x14_3xD4x12_4xD3x10.stl")
out["Perni"] = {"vol_cm3": round(tp.volume / 1000, 3), "watertight": bool(tp.is_watertight), "isole": len(tp.split(only_watertight=False))}
for f in ["Karna_Ala_Xneg.stl", "Karna_Ala_Xpos.stl"]: shutil.copy(V3 + f, V4 + f)
rep["pezzi"] = out
rep["perni"] = "anima d/2 (gioco 0.12 nel foro d+0.24), 3 alette 0.6 mm che arrivano a 0.10 mm oltre il foro, rampe 1.5 mm e smussi 0.4 alle punte"
json.dump(rep, open(V4 + "karna_v4_magneti.json", "w", encoding="utf8"), indent=1)
print(json.dumps(rep, indent=1)); print("tempo", round(time.time() - t0, 1), "s")
