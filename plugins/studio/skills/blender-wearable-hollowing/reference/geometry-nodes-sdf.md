# Geometry Nodes SDF / boolean recipes (Blender 4.2+, verified in 5.1)

## Node ids and sockets

| Purpose | `bl_idname` | Inputs that matter |
|---|---|---|
| mesh → signed distance grid | `GeometryNodeMeshToSDFGrid` | `Mesh`, `Voxel Size`, `Band Width` (voxels, ≥ offset/voxel + 3) |
| grow / shrink | `GeometryNodeSDFGridOffset` | `Grid`, `Distance` (negative = erode) |
| union / intersect / difference | `GeometryNodeSDFGridBoolean` (`operation`) | UNION, INTERSECT: all on `'Grid'`; DIFFERENCE: `'Grid 1'` minus `'Grid 2'` (multi) |
| grid → mesh | `GeometryNodeGridToMesh` | `Grid`, **`Threshold` = 0.0** (default 0.1 gives an empty mesh), `Adaptivity` |
| smooth positions | `GeometryNodeBlurAttribute` (`data_type='FLOAT_VECTOR'`) | `Value` ← Position node, `Iterations` |
| mesh boolean | `GeometryNodeMeshBoolean` (`operation`, `solver='EXACT'`) | DIFFERENCE: `'Mesh 1'`, `'Mesh 2'`; UNION/INTERSECT: `inputs[1]` (multi) |
| read another object | `GeometryNodeObjectInfo` | `Object`, `transform_space` ORIGINAL/RELATIVE; returns **evaluated** geometry |
| switch | `GeometryNodeSwitch` (`input_type='GEOMETRY'`) | `Switch`, `False`, `True` |

Inspect sockets instead of guessing: `[(s.name, s.identifier, s.enabled, s.is_multi_input) for s in node.inputs]`.
Inputs are addressed by **name** (`node.inputs['Grid 1']`); the identifier of a multi-input differs from its name.

## Building a group from Python

```python
ng = bpy.data.node_groups.get(NAME) or bpy.data.node_groups.new(NAME, 'GeometryNodeTree')
ng.is_modifier = True
ng.nodes.clear()
for it in list(ng.interface.items_tree): ng.interface.remove(it)
ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
s = ng.interface.new_socket("Spessore parete", in_out='INPUT', socket_type='NodeSocketFloat')
s.default_value, s.min_value, s.max_value = 0.04, 0.01, 0.1

def nd(idn, x, y, **props):
    n = ng.nodes.new(idn); n.location = (x, y)
    for k, v in props.items(): setattr(n, k, v)
    if idn == 'GeometryNodeGridToMesh': n.inputs['Threshold'].default_value = 0.0
    return n
def L(a, out, b, inp): ng.links.new(a.outputs[out], b.inputs[inp])
```

Modifier values: `md = obj.modifiers.new(name, 'NODES'); md.node_group = ng;
ids = {it.name: it.identifier for it in ng.interface.items_tree if it.item_type == 'SOCKET' and it.in_out == 'INPUT'};
md[ids['Taglia occhi']] = False`. Then force the update:

```python
md.show_viewport = False; md.show_viewport = True
obj.update_tag(); bpy.context.view_layer.update()
ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
```

Warnings: `md.node_warnings` exists but was empty even when Grid to Mesh produced nothing; test
sub-results by temporarily linking an intermediate node to the Group Output.

## Measuring the result with numpy (fast, 2M vertices ok)

```python
n = len(me.vertices); co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
def spans(v):                      # clusters of sorted coordinates = wall crossings
    if len(v) == 0: return []
    cuts = np.where(np.diff(v) > 0.02)[0]; segs = []; start = 0
    for c in list(cuts) + [len(v) - 1]:
        segs.append((round(float(v[start]), 3), round(float(v[c]), 3))); start = c + 1
    return segs
for z in (-0.4, -0.2, 0.0, 0.2):
    s = co[np.abs(co[:, 2] - z) < 0.003]
    print(z, spans(np.sort(s[np.abs(s[:, 0]) < 0.006][:, 1])), spans(np.sort(s[np.abs(s[:, 1]) < 0.006][:, 0])))
```

Two clusters = one wall (outer, inner surface); their distance is the wall thickness; the gap between
walls is the cavity. A cluster that spans a long range at one z is a floor or a flat cut.

Other checks: `sum(1 for e in bm.edges if not e.is_manifold)` (0 for a printable shell; one 4-face edge
where a cone grazes the cavity is harmless), signed volume for orientation, "vertices inside the hole
ellipse along the whole depth == 0" for a through-hole.

## Helper geometry built in Python (closed, outward normals)

- Lathe / stepped cylinder: rings `(ax, az, depth)` along a frame `(c, n, u, w)`, quads between rings,
  fan caps; `bmesh.ops.recalc_face_normals` after `from_pydata`.
- Heightfield solid: top grid z = f(x, y), copy at z = −1.2, side quads along the four borders.
- Prism from a polar outline: 1440 angular bins of max radius, `np.interp(..., period=NB)` for empty
  bins, moving-average low-pass (W = 61) for a clean rim, high-pass for "lock" bumps.
- Always `remove_doubles(dist=1e-7)` and `recalc_face_normals` before using a helper in a boolean.

## Baking and cleaning

```python
me = bpy.data.meshes.new_from_object(src.evaluated_get(dg)); ob = bpy.data.objects.new(name, me)
```

Keep the procedural object hidden, show the bake for sculpting. Do not run a Remesh modifier on the
bake: it rounds holes and magnet pockets. For more detail lower the group's voxel size and bake again.

## Section view for a quick visual check

Duplicate the evaluated mesh, `bmesh.ops.bisect_plane(plane_no=(1,0,0), clear_outer=True)`, move it
aside, look from +x. Delete it afterwards (and restore any object you hid or moved).
