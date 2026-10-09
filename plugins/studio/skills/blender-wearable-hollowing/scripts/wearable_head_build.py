# Full build of a hollow wearable head with removable magnetic eyes (Blender 5.1, Geometry Nodes SDF).
# Example from the "Riot" king head: adapt object names, eye centres/normals, outline levels and beard
# footprint to the new model (see SKILL.md). Run in Blender: Text Editor > Run Script.

# Elmo indossabile "Riot" - build procedurale (Blender 5.1)
# Esegui in Blender (Text Editor > Run Script) per rigenerare helper + Geometry Nodes.
# Cambia SCALE_CM se cambi l'altezza di stampa: le sedi magnete sono in mm reali.
import bpy, bmesh, math
import numpy as np

# ------------------------------------------------------------------ parametri
SCALE_CM     = 50.0        # altezza di stampa prevista del modello (modello = 1 m)
MAG_D, MAG_H = 8.0, 3.0    # magnete consigliato 8x3 mm (neodimio)
POCKET_D     = MAG_D + 0.5 # sede magnete (mm reali)
POCKET_H     = MAG_H + 0.4 # profondita' sede per lato (il cilindro attraversa il gioco: meta' nel tappo, meta' nella parete)
CLEAR        = 0.4         # gioco radiale tappo/foro (mm)
EYE_AX, EYE_AZ = 0.052, 0.034   # semiassi ellisse occhio (unita' modello)
EYE_TILT_DEG = 8.0
SRC_NAME     = 'geometry_0_backup'   # originale ad alta risoluzione (aperto sotto): usato per le misure
SDF_SRC_NAME = 'geometry_0'          # versione chiusa/manifold: usata per l'SDF

f = SCALE_CM / 100.0
def mm(v): return v / 1000.0 / f

SRC = bpy.data.objects[SRC_NAME]
me  = SRC.data
nv  = len(me.vertices)
co  = np.empty(nv * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)

def get_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c

HC = get_coll("Elmo_helpers")
OC = get_coll("Elmo_output")

# copia SENZA modificatori della testa chiusa (Object Info legge la geometria valutata,
# quindi non posso puntare direttamente a geometry_0 che ha ancora il vecchio modificatore)
SDF_SRC = bpy.data.objects.get("H_testa_chiusa")
if SDF_SRC is None:
    SDF_SRC = bpy.data.objects.new("H_testa_chiusa", bpy.data.objects[SDF_SRC_NAME].data)
    HC.objects.link(SDF_SRC)

def replace_obj(name, verts, faces, coll):
    old = bpy.data.objects.get(name)
    if old is not None:
        m = old.data
        bpy.data.objects.remove(old)
        if m and m.users == 0: bpy.data.meshes.remove(m)
    m = bpy.data.meshes.new(name)
    m.from_pydata([tuple(v) for v in verts], [], [tuple(fc) for fc in faces])
    m.validate(); m.update()
    bm = bmesh.new(); bm.from_mesh(m)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(m); bm.free()
    o = bpy.data.objects.new(name, m); coll.objects.link(o)
    return o

# ------------------------------------------------------------------ 1. profilo capelli a z0
CY, Z0, NB = 0.03, -0.13, 1440
sl  = co[np.abs(co[:, 2] - Z0) < 0.003]
ang = np.arctan2(sl[:, 1] - CY, sl[:, 0]); rad = np.hypot(sl[:, 0], sl[:, 1] - CY)
b   = np.floor((ang + np.pi) / (2 * np.pi) * NB).astype(int) % NB
rmax = np.zeros(NB); np.maximum.at(rmax, b, rad)
idx = np.arange(NB); good = rmax > 0
rmax = np.interp(idx, idx[good], rmax[good], period=NB)
k = np.array([1, 2, 3, 2, 1]) / 9.0
rsm = np.convolve(np.concatenate([rmax[-2:], rmax, rmax[:2]]), k, 'valid')
W = 61
rlow = np.convolve(np.concatenate([rsm[-(W // 2):], rsm, rsm[:W // 2]]), np.ones(W) / W, 'valid')
bump = rsm - rlow; bumpn = bump / (np.abs(bump).max() + 1e-9)
theta = (idx + 0.5) / NB * 2 * np.pi - np.pi

# ------------------------------------------------------------------ 2. gonna capelli (solido chiuso)
ZTOP, ZBOT, NZ, EX = -0.10, -0.60, 51, 0.36
TAPER = 0.93   # scala del profilo in fondo alla gonna (1 = verticale)
def yfront(z): return -0.13 - 0.30 * max(0.0, -0.12 - z)
zs = np.linspace(ZTOP, ZBOT, NZ)
verts = []
for z in zs:
    s  = 1.0 - (1.0 - TAPER) * (ZTOP - z) / (ZTOP - ZBOT)
    rr = rsm * s + 0.004 * np.sin(7 * theta + 20 * z)
    ey = CY - yfront(z)
    re = 1.0 / np.sqrt((np.cos(theta) / EX) ** 2 + (np.sin(theta) / ey) ** 2)
    kk = 0.03
    h  = np.clip(0.5 + 0.5 * (re - rr) / kk, 0, 1)
    rmin = re * (1 - h) + rr * h - kk * h * (1 - h)
    rfin = np.where(np.sin(theta) < 0, rmin, rr)
    x = rfin * np.cos(theta); y = CY + rfin * np.sin(theta)
    verts += [(float(x[i]), float(y[i]), float(z)) for i in range(NB)]
faces = []
for r in range(NZ - 1):
    for i in range(NB):
        a = r * NB + i; bb = r * NB + (i + 1) % NB
        faces.append((a, bb, bb + NB, a + NB))
ct = len(verts); verts.append((0.0, CY, float(ZTOP)))
for i in range(NB): faces.append((ct, (i + 1) % NB, i))
cb = len(verts); verts.append((0.0, CY, float(ZBOT))); base = (NZ - 1) * NB
for i in range(NB): faces.append((cb, base + i, base + (i + 1) % NB))
ext = replace_obj("H_estensione_capelli", verts, faces, HC)

# ------------------------------------------------------------------ 3. taglio fondo (heightfield chiuso)
N = 281; xs = np.linspace(-0.75, 0.75, N)
X, Y = np.meshgrid(xs, xs)
th = np.arctan2(Y - CY, X)
bi = np.floor((th + np.pi) / (2 * np.pi) * NB).astype(int) % NB
# impronta della punta della barba (z < -0.44): ellisse centrata davanti
BEARD_C, BEARD_AX, BEARD_AY = (0.0, -0.31), 0.11, 0.12
e_beard = np.hypot(X / BEARD_AX, (Y - BEARD_C[1]) / BEARD_AY)
dip = -0.11 * np.clip((1.15 - e_beard) / 0.30, 0, 1)      # il taglio scende solo sotto la barba
basez = -0.455 - 0.012 * np.clip(np.sin(th), 0, 1)
ZC = basez - 0.02 * bumpn[bi] + 0.012 * np.sin(5 * th + 1.0) + dip
ZB = -1.2
verts = [(float(X[j, i]), float(Y[j, i]), float(ZC[j, i])) for j in range(N) for i in range(N)]
verts += [(float(X[j, i]), float(Y[j, i]), ZB) for j in range(N) for i in range(N)]
faces = []
T = lambda j, i: j * N + i
B = lambda j, i: N * N + j * N + i
for j in range(N - 1):
    for i in range(N - 1):
        faces.append((T(j, i), T(j, i + 1), T(j + 1, i + 1), T(j + 1, i)))
        faces.append((B(j, i), B(j + 1, i), B(j + 1, i + 1), B(j, i + 1)))
for i in range(N - 1):
    faces.append((T(0, i), B(0, i), B(0, i + 1), T(0, i + 1)))
    faces.append((T(N - 1, i), T(N - 1, i + 1), B(N - 1, i + 1), B(N - 1, i)))
for j in range(N - 1):
    faces.append((T(j, 0), T(j + 1, 0), B(j + 1, 0), B(j, 0)))
    faces.append((T(j, N - 1), B(j, N - 1), B(j + 1, N - 1), T(j + 1, N - 1)))
cut = replace_obj("H_taglio_fondo", verts, faces, HC)

# intaglio: toglie la gonna dall'impronta della barba sotto z=-0.40 (evita doppie pareti/pinne dietro la barba)
NS = 96; nv_ = []; nf_ = []
for zz in (-0.40, -1.0):
    for i in range(NS):
        t = 2 * math.pi * i / NS
        nv_.append((BEARD_C[0] + (BEARD_AX + 0.015) * math.cos(t), BEARD_C[1] + (BEARD_AY + 0.015) * math.sin(t), zz))
for i in range(NS):
    nf_.append((i, (i + 1) % NS, NS + (i + 1) % NS, NS + i))
nv_.append((BEARD_C[0], BEARD_C[1], -0.40)); nv_.append((BEARD_C[0], BEARD_C[1], -1.0))
for i in range(NS):
    nf_.append((2 * NS, (i + 1) % NS, i)); nf_.append((2 * NS + 1, NS + i, NS + (i + 1) % NS))
notch = replace_obj("H_intaglio_barba", nv_, nf_, HC)

# ------------------------------------------------------------------ 4. occhi: cutter, tappi, sedi magnete
def norm(v): v = np.asarray(v, float); return v / np.linalg.norm(v)
def lathe(c, n, u, w, rings, segs=96):
    vs = []; fs = []
    for ax, az, d in rings:
        for i in range(segs):
            t = 2 * math.pi * i / segs
            vs.append(tuple(c + n * d + u * (ax * math.cos(t)) + w * (az * math.sin(t))))
    for kq in range(len(rings) - 1):
        for i in range(segs):
            a = kq * segs + i; bb = kq * segs + (i + 1) % segs
            fs.append((a, bb, bb + segs, a + segs))
    c0 = len(vs); vs.append(tuple(c + n * rings[0][2]))
    for i in range(segs): fs.append((c0, (i + 1) % segs, i))
    c1 = len(vs); vs.append(tuple(c + n * rings[-1][2])); base = (len(rings) - 1) * segs
    for i in range(segs): fs.append((c1, base + i, base + (i + 1) % segs))
    return vs, fs

hp = mm(POCKET_H); cl = mm(CLEAR); pr = mm(POCKET_D) / 2
TAPER_K = 0.10            # conicita' del foro: raggio -1 mm ogni 10 mm di profondita' (~6 gradi)
POCKET_MIN_DEPTH = 0.012  # centro sede almeno a 12 mm (modello) dalla superficie nominale
WALL_T = 0.04             # spessore parete nominale (stesso valore del modificatore)
cutters, plugs, pockets, report = [], [], [], []
for sx, tag in ((-1, 'SX'), (1, 'DX')):
    # n punta VERSO L'INTERNO della testa: profondita' positiva = dentro la parete
    c = np.array([sx * 0.094, -0.30, 0.003]); n = -norm([sx * 0.085, -0.99, -0.12])
    u = norm(np.cross([0, 0, 1.0], n)); w = np.cross(n, u)
    tilt = math.radians(EYE_TILT_DEG * sx)
    ur = u * math.cos(tilt) + w * math.sin(tilt); wr = -u * math.sin(tilt) + w * math.cos(tilt)
    d = co - c; depth = d @ n; a = d @ ur; bb = d @ wr
    front = (co[:, 1] < -0.2) & (depth > -0.08) & (depth < 0.08)
    # foro passante leggermente conico (piu' largo fuori): il tappo entra da fuori e non puo' cadere dentro
    K = TAPER_K
    rings_c = [(EYE_AX + K * 0.12, EYE_AZ + K * 0.12, -0.12), (EYE_AX - K * 0.25, EYE_AZ - K * 0.25, 0.25)]
    rings_p = [(EYE_AX + K * 0.12 - cl, EYE_AZ + K * 0.12 - cl, -0.12), (EYE_AX - K * 0.25 - cl, EYE_AZ - K * 0.25 - cl, 0.25)]
    vs, fs = lathe(c, n, ur, wr, rings_c); cutters.append(replace_obj("H_occhio_cutter_" + tag, vs, fs, HC))
    vs, fs = lathe(c, n, ur, wr, rings_p); plugs.append(replace_obj("H_occhio_tappo_solido_" + tag, vs, fs, HC))
    # sedi magnete radiali: una sopra e una sotto, a cavallo del bordo del foro (meta' nel tappo, meta' nella parete)
    for j, sgn in enumerate((+1, -1)):
        loc = front & (np.abs(a) < pr + mm(2.0)) & (np.abs(bb - sgn * EYE_AZ) < pr + mm(2.0))
        smax = float(depth[loc].max()) if loc.any() else 0.0        # punto piu' incassato della superficie esterna li' vicino
        dc = max(smax + mm(1.5) + pr, POCKET_MIN_DEPTH)              # profondita' del centro sede (asse parallelo alla superficie)
        bz = EYE_AZ - K * dc                                          # semiasse verticale del foro a quella profondita'
        pc = c + n * dc + wr * (sgn * bz)
        vs, fs = lathe(pc, sgn * wr, ur, n, [(pr, pr, -hp), (pr, pr, hp)], segs=48)
        pockets.append(replace_obj("H_sede_magnete_%s%d" % (tag, j + 1), vs, fs, HC))
        wall_est = WALL_T - (dc + pr)
        ok = 'OK' if wall_est > mm(1.5) else 'ATTENZIONE: sede vicina alla cavita'
        report.append("occhio %s sede %s: superficie a %.1f mm, centro sede a %.1f mm, resta %.1f mm verso la cavita -> %s" % (tag, 'sopra' if sgn > 0 else 'sotto', smax * 1000 * f, dc * 1000 * f, wall_est * 1000 * f, ok))

for o in HC.objects:
    o.hide_render = True
HC.hide_viewport = True

# ------------------------------------------------------------------ 4b. apertura larga sotto (variante senza gonna)
# prisma verticale = sezione della testa a Z_OPEN ristretta di (parete + margine), da Z_OPEN verso il basso.
# Toglie solo la parete nascosta sotto (fondo del collo / retro della barba); profilo esterno di capelli e barba intatto.
Z_OPEN = -0.24            # livello a cui si misura la sezione (impronta dell'apertura)
Z_TOP = -0.11             # il prisma sale fin qui: sopra la conca del fondo originale (apice a z=-0.172) + parete
SHRINK = WALL_T + 0.012
sl2 = co[np.abs(co[:, 2] - Z_OPEN) < 0.003]
ang2 = np.arctan2(sl2[:, 1] - CY, sl2[:, 0]); rad2 = np.hypot(sl2[:, 0], sl2[:, 1] - CY)
b2 = np.floor((ang2 + np.pi) / (2 * np.pi) * NB).astype(int) % NB
r2 = np.zeros(NB); np.maximum.at(r2, b2, rad2)
good2 = r2 > 0
r2 = np.interp(idx, idx[good2], r2[good2], period=NB)
r2 = np.convolve(np.concatenate([r2[-(W // 2):], r2, r2[:W // 2]]), np.ones(W) / W, 'valid') - SHRINK
pv = [(float(r2[i] * np.cos(theta[i])), float(CY + r2[i] * np.sin(theta[i])), Z_TOP) for i in range(NB)]
pv += [(x, y, -1.0) for x, y, _ in pv]
pf = [(i, (i + 1) % NB, NB + (i + 1) % NB, NB + i) for i in range(NB)]
pv.append((0.0, CY, Z_TOP)); pv.append((0.0, CY, -1.0))
for i in range(NB):
    pf.append((2 * NB, (i + 1) % NB, i)); pf.append((2 * NB + 1, NB + i, NB + (i + 1) % NB))
opening = replace_obj("H_apertura_fondo", pv, pf, HC)
report.append("apertura sotto (variante originale): larghezza %.0f cm, profondita %.0f cm a scala %.0f cm" % (
    (r2[idx[np.abs(theta) < 0.02]].mean() * 2) * 100 * f, (r2[idx[np.abs(theta - np.pi / 2) < 0.02]].mean() + r2[idx[np.abs(theta + np.pi / 2) < 0.02]].mean()) * 100 * f, SCALE_CM))

for o in HC.objects:
    o.hide_render = True
HC.hide_viewport = True

# ------------------------------------------------------------------ 5. Geometry Nodes (una funzione, due varianti)
def build_group(NGN, with_skirt, cutter_obj):
    ng = bpy.data.node_groups.get(NGN)
    if ng is None:
        ng = bpy.data.node_groups.new(NGN, 'GeometryNodeTree')
        ng.is_modifier = True
    ng.nodes.clear()
    for it in list(ng.interface.items_tree):
        ng.interface.remove(it)
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    def sock(name, stype, default, mn=None, mx=None):
        s = ng.interface.new_socket(name, in_out='INPUT', socket_type=stype)
        s.default_value = default
        if mn is not None: s.min_value = mn
        if mx is not None: s.max_value = mx
        return s
    sock("Spessore parete", 'NodeSocketFloat', WALL_T, 0.01, 0.1)
    sock("Precisione voxel", 'NodeSocketFloat', 0.004, 0.002, 0.02)
    sock("Lisciatura interno", 'NodeSocketInt', 120, 0, 500)
    sock("Adattivita mesh", 'NodeSocketFloat', 0.0, 0.0, 1.0)
    sock("Scava", 'NodeSocketBool', True)
    sock("Taglia occhi", 'NodeSocketBool', True)
    sock("Output tappi occhi", 'NodeSocketBool', False)

    def nd(idn, x, y, **props):
        n = ng.nodes.new(idn); n.location = (x, y)
        for kk, vv in props.items(): setattr(n, kk, vv)
        if idn == 'GeometryNodeGridToMesh':
            n.inputs['Threshold'].default_value = 0.0   # iso-superficie dell'SDF (default 0.1 = mesh vuota)
        return n
    def L(a, out, bnode, inp):
        ng.links.new(a.outputs[out], bnode.inputs[inp])
    def objinfo(ob, x, y):
        n = nd('GeometryNodeObjectInfo', x, y); n.inputs['Object'].default_value = ob; n.transform_space = 'ORIGINAL'; return n
    def sdf(x, y):
        s = nd('GeometryNodeMeshToSDFGrid', x, y); s.inputs['Band Width'].default_value = 16
        L(gi, 'Precisione voxel', s, 'Voxel Size'); return s

    gi = nd('NodeGroupInput', -1400, 0); go = nd('NodeGroupOutput', 2600, 0)
    oi_t = objinfo(SDF_SRC, -1200, 300); sdf_t = sdf(-1000, 300); L(oi_t, 'Geometry', sdf_t, 'Mesh')
    oi_c = objinfo(cutter_obj, -1200, -100); sdf_c = sdf(-1000, -100); L(oi_c, 'Geometry', sdf_c, 'Mesh')
    if with_skirt:
        oi_e = objinfo(ext, -1200, 100); sdf_e = sdf(-1000, 100); L(oi_e, 'Geometry', sdf_e, 'Mesh')
        oi_n = objinfo(notch, -1200, -500); sdf_n = sdf(-1000, -500); L(oi_n, 'Geometry', sdf_n, 'Mesh')
        skirt = nd('GeometryNodeSDFGridBoolean', -900, 50, operation='DIFFERENCE')
        L(sdf_e, 'SDF Grid', skirt, 'Grid 1'); L(sdf_n, 'SDF Grid', skirt, 'Grid 2')
        uni = nd('GeometryNodeSDFGridBoolean', -800, 250, operation='UNION')
        L(sdf_t, 'SDF Grid', uni, 'Grid'); L(skirt, 'Grid', uni, 'Grid')
        solid_out = (uni, 'Grid')
    else:
        solid_out = (sdf_t, 'SDF Grid')
    neg = nd('ShaderNodeMath', -800, 0, operation='MULTIPLY'); neg.inputs[1].default_value = -1.0
    L(gi, 'Spessore parete', neg, 0)
    off = nd('GeometryNodeSDFGridOffset', -600, 100); L(solid_out[0], solid_out[1], off, 'Grid'); L(neg, 'Value', off, 'Distance')
    g2m_in = nd('GeometryNodeGridToMesh', -400, 100); L(off, 'Grid', g2m_in, 'Grid')
    pos = nd('GeometryNodeInputPosition', -400, -100)
    blur = nd('GeometryNodeBlurAttribute', -200, -50, data_type='FLOAT_VECTOR')
    L(pos, 'Position', blur, 'Value'); L(gi, 'Lisciatura interno', blur, 'Iterations')
    setp = nd('GeometryNodeSetPosition', 0, 100); L(g2m_in, 'Mesh', setp, 'Geometry'); L(blur, 'Value', setp, 'Position')
    sdf_in = nd('GeometryNodeMeshToSDFGrid', 200, 100); sdf_in.inputs['Band Width'].default_value = 6
    L(setp, 'Geometry', sdf_in, 'Mesh'); L(gi, 'Precisione voxel', sdf_in, 'Voxel Size')
    shell = nd('GeometryNodeSDFGridBoolean', 400, 200, operation='DIFFERENCE')
    L(solid_out[0], solid_out[1], shell, 'Grid 1'); L(sdf_in, 'SDF Grid', shell, 'Grid 2')
    cutg = nd('GeometryNodeSDFGridBoolean', 600, 150, operation='DIFFERENCE')
    L(shell, 'Grid', cutg, 'Grid 1'); L(sdf_c, 'SDF Grid', cutg, 'Grid 2')
    g2m = nd('GeometryNodeGridToMesh', 800, 150); L(cutg, 'Grid', g2m, 'Grid'); L(gi, 'Adattivita mesh', g2m, 'Adaptivity')
    g2m_full = nd('GeometryNodeGridToMesh', 800, 400); L(solid_out[0], solid_out[1], g2m_full, 'Grid'); L(gi, 'Adattivita mesh', g2m_full, 'Adaptivity')
    sw_scava = nd('GeometryNodeSwitch', 1000, 250, input_type='GEOMETRY')
    L(gi, 'Scava', sw_scava, 'Switch'); L(g2m_full, 'Mesh', sw_scava, 'False'); L(g2m, 'Mesh', sw_scava, 'True')
    # elmo: differenza cutter occhi + sedi
    jn_cut = nd('GeometryNodeJoinGeometry', 1000, -200)
    for i, ob in enumerate(cutters + pockets):
        o_ = objinfo(ob, 800, -300 - 120 * i); ng.links.new(o_.outputs['Geometry'], jn_cut.inputs[0])
    mb_elmo = nd('GeometryNodeMeshBoolean', 1300, 150, operation='DIFFERENCE', solver='EXACT')
    L(sw_scava, 'Output', mb_elmo, 'Mesh 1'); L(jn_cut, 'Geometry', mb_elmo, 'Mesh 2')
    sw_eyes = nd('GeometryNodeSwitch', 1600, 150, input_type='GEOMETRY')
    L(gi, 'Taglia occhi', sw_eyes, 'Switch'); L(sw_scava, 'Output', sw_eyes, 'False'); L(mb_elmo, 'Mesh', sw_eyes, 'True')
    # tappi: blocco locale (guscio scavato ∩ box occhi) ∩ solido tappo, meno sedi  -> booleani su mesh piccola
    box = nd('GeometryNodeMeshCube', -400, -900); box.inputs['Size'].default_value = (0.46, 0.24, 0.22)
    box_tr = nd('GeometryNodeTransform', -200, -900); box_tr.inputs['Translation'].default_value = (0.0, -0.26, 0.0)
    L(box, 'Mesh', box_tr, 'Geometry')
    sdf_box = sdf(0, -900); L(box_tr, 'Geometry', sdf_box, 'Mesh')
    blk = nd('GeometryNodeSDFGridBoolean', 200, -900, operation='INTERSECT')
    L(cutg, 'Grid', blk, 'Grid'); L(sdf_box, 'SDF Grid', blk, 'Grid')
    g2m_blk = nd('GeometryNodeGridToMesh', 400, -900); L(blk, 'Grid', g2m_blk, 'Grid')
    jn_plug = nd('GeometryNodeJoinGeometry', 1000, -1200)
    for i, ob in enumerate(plugs):
        o_ = objinfo(ob, 800, -1200 - 120 * i); ng.links.new(o_.outputs['Geometry'], jn_plug.inputs[0])
    mb_int = nd('GeometryNodeMeshBoolean', 1300, -900, operation='INTERSECT', solver='EXACT')
    ng.links.new(g2m_blk.outputs['Mesh'], mb_int.inputs[1]); ng.links.new(jn_plug.outputs['Geometry'], mb_int.inputs[1])
    jn_pk = nd('GeometryNodeJoinGeometry', 1000, -1600)
    for i, ob in enumerate(pockets):
        o_ = objinfo(ob, 800, -1600 - 120 * i); ng.links.new(o_.outputs['Geometry'], jn_pk.inputs[0])
    mb_plug = nd('GeometryNodeMeshBoolean', 1600, -900, operation='DIFFERENCE', solver='EXACT')
    L(mb_int, 'Mesh', mb_plug, 'Mesh 1'); L(jn_pk, 'Geometry', mb_plug, 'Mesh 2')
    sw_out = nd('GeometryNodeSwitch', 2200, 0, input_type='GEOMETRY')
    L(gi, 'Output tappi occhi', sw_out, 'Switch'); L(sw_eyes, 'Output', sw_out, 'False'); L(mb_plug, 'Mesh', sw_out, 'True')
    L(sw_out, 'Output', go, 'Geometry')
    return ng

# ------------------------------------------------------------------ 6. oggetti output
def out_obj(name, ng, tappi, location):
    o = bpy.data.objects.get(name)
    if o is None:
        m = bpy.data.meshes.new(name); o = bpy.data.objects.new(name, m); OC.objects.link(o)
        o.location = location
    for md in list(o.modifiers): o.modifiers.remove(md)
    md = o.modifiers.new(ng.name, 'NODES'); md.node_group = ng
    md.show_viewport = False   # attivalo a mano: il calcolo completo richiede ~15 s
    for it in ng.interface.items_tree:
        if it.item_type == 'SOCKET' and it.in_out == 'INPUT' and it.name == "Output tappi occhi":
            md[it.identifier] = tappi
    return o

ng3 = build_group("Elmo_v3", True, cut)            # variante con gonna di capelli
out_obj("Elmo_v3", ng3, False, (0, 0, 0))
out_obj("Elmo_v3_tappi_occhi", ng3, True, (0, -0.35, 0))
ng4 = build_group("Elmo_v4_originale", False, opening)   # variante originale: collo intatto, apertura larga sotto
out_obj("Elmo_v4_originale", ng4, False, (-2.0, 0, 0))
out_obj("Elmo_v4_originale_tappi", ng4, True, (-2.0, -0.35, 0))
print("\n".join(report))
print("BUILD OK")
