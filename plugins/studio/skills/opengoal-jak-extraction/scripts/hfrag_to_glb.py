"""Build the desert floor (the hfrag height field) as .glb files.

    python tools/glb/hfrag_to_glb.py DESERT.fr3 WANG.png MIP.png OUT.glb COLLISION.glb [--sand TILE.png [--sand-quads N]]

Jak 3 draws the desert's dunes with a renderer of their own (hfrag) that the glb ripper skips:
only rocks, plants and the city come out. OpenGOAL's extractor does keep the field in the
level's .fr3 (tfrag3::Level::hfrag, format version 43): a 512 x 512 grid of heights, 8 m apart
from the world origin (hfrag.vert: x = 32768 * (vi % 512), z = 32768 * (vi / 512)), each vertex
with an index into the level's time-of-day colors. The .fr3 is zstd after an 8 byte size.

The vertex array is found by its shape: a u64 count followed by 16 byte HfragmentVertex
records {f32 height, u32 vi, u16 color_index, u8 u, u8 v, u32 pad = 0}; the indices, corners,
buckets and PackedTimeOfDay (8 palettes x RGBA per color) follow it.

OUT.glb gets the full grid (GOAL world space in meters, like the ripped levels) with the
sand texture: WANG.png is the game's 512 x 256 atlas of 32 px Wang tiles, whose edges only
match in the right combinations (laid out as-is it shows a grid of seams). They are composed
into a seamless, periodic 32 x 32 tile texture (two tiles per 8 m quad side), re-tiled from
random soft patches so the tiles' lattice of blobs does not show, and brought to the
brightness of its own mip (MIP.png) the way the PS2 doubled it.
COLLISION.glb is the same field at half resolution.
"""

import compression.zstd
import json
import math
import struct
import sys
import zlib
from pathlib import Path

EDGE = 512            # vertices per side
SPACING = 8.0         # meters between vertices (32768 units)
UNITS = 4096.0        # GOAL units per meter
WANG_TILE = 32        # pixels per Wang tile in the atlas
WANG_GRID = 32        # tiles per side of the composed sand texture
TILE_QUADS = WANG_GRID // 2  # quads per texture repeat: two tiles per quad side (4 m)
DAY_PALETTES = range(4)  # time-of-day palettes 0-3 are daylight (4-7 dusk and night)


def read_png(path):
    data = Path(path).read_bytes()
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        size, kind = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + size]
        pos += 12 + size
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and color == 6, "expects 8 bit RGBA"
        elif kind == b"IDAT":
            idat += body
    raw, stride = zlib.decompress(idat), width * 4
    pixels, previous, i = bytearray(), bytearray(stride), 0
    for _ in range(height):
        kind, line = raw[i], bytearray(raw[i + 1 : i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - 4] if x >= 4 else 0
            b = previous[x]
            c = previous[x - 4] if x >= 4 else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        pixels += line
        previous = line
    return width, height, pixels


def png_bytes(width, height, pixels):
    raw = b"".join(b"\0" + bytes(pixels[y * width * 4 : (y + 1) * width * 4]) for y in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def wang_compose(width, atlas, seed=3):
    """A periodic WANG_GRID x WANG_GRID texture of atlas tiles whose shared edges match.

    The atlas (16 x 8 tiles) is indexed by edge colors: in column c the left/right edges are
    (L, R) = divmod(c % 8, 3) (3 colors, every pair but (2, 2)) and in row r the top edge is
    r // 2, the bottom 2 * (r % 2) + c // 8 (4 colors, every pair)."""
    import random
    rng = random.Random(seed)
    n, t = WANG_GRID, WANG_TILE
    # Vertical edge colors: vertical[y][x] is the left edge of tile (x, y), wrapping around;
    # resample a row until it has no (2, 2) tile.
    vertical = []
    for _ in range(n):
        while True:
            row = [rng.randrange(3) for _ in range(n)]
            if not any(row[x] == 2 and row[(x + 1) % n] == 2 for x in range(n)):
                break
        vertical.append(row)
    horizontal = [[rng.randrange(4) for _ in range(n)] for _ in range(n)]  # top edge of (x, y)
    size = n * t
    out = bytearray(size * size * 4)
    for y in range(n):
        for x in range(n):
            left, right = vertical[y][x], vertical[y][(x + 1) % n]
            top, bottom = horizontal[y][x], horizontal[(y + 1) % n][x]
            column = (bottom % 2) * 8 + left * 3 + right
            row = top * 2 + bottom // 2
            for py in range(t):
                src = ((row * t + py) * width + column * t) * 4
                dst = ((y * t + py) * size + x * t) * 4
                out[dst : dst + t * 4] = atlas[src : src + t * 4]
    return size, out


def quilt(size, pixels, patch=96, step=64, seed=7):
    """Re-tile a periodic texture from soft-edged patches taken at random offsets (and
    flips), still periodic. Each Wang tile has a bright blob in the middle, so the composed
    texture shows a regular 32 px lattice; patches from arbitrary offsets break it up."""
    import math
    import random
    rng = random.Random(seed)
    window = [math.sin(math.pi * (i + 0.5) / patch) ** 2 for i in range(patch)]
    acc = [0.0] * (size * size * 3)
    weight = [0.0] * (size * size)
    for oy in range(0, size, step):
        for ox in range(0, size, step):
            sx, sy = rng.randrange(size), rng.randrange(size)
            flip_x, flip_y = rng.random() < 0.5, rng.random() < 0.5
            for py in range(patch):
                wy = window[py]
                src_y = (sy + (patch - 1 - py if flip_y else py)) % size
                dst_y = (oy + py) % size
                for px in range(patch):
                    w = wy * window[px]
                    src = (src_y * size + (sx + (patch - 1 - px if flip_x else px)) % size) * 4
                    dst = dst_y * size + (ox + px) % size
                    weight[dst] += w
                    a = dst * 3
                    acc[a] += w * pixels[src]
                    acc[a + 1] += w * pixels[src + 1]
                    acc[a + 2] += w * pixels[src + 2]
    out = bytearray(size * size * 4)
    for i in range(size * size):
        w = weight[i]
        out[i * 4] = round(acc[i * 3] / w)
        out[i * 4 + 1] = round(acc[i * 3 + 1] / w)
        out[i * 4 + 2] = round(acc[i * 3 + 2] / w)
        out[i * 4 + 3] = 128
    return out


def find_vertices(data):
    """Offset of the u64 count before the hfrag vertex records."""
    for offset in range(0, len(data) - 8, 4):
        count = struct.unpack_from("<Q", data, offset)[0]
        # Whole quads (4 vertices each), at least a row of them.
        if not EDGE <= count <= EDGE * EDGE * 4 or count % 4 or offset + 8 + count * 16 > len(data):
            continue
        ok = True
        for k in [*range(0, count, max(1, count // 64)), count - 1]:
            height, vi, color, u, v, pad = struct.unpack_from("<fIHBBI", data, offset + 8 + k * 16)
            if pad or u > 1 or v > 1 or vi >= EDGE * EDGE or not 0 <= height < 600000 or color >= 4096:
                ok = False
                break
        if ok:
            return offset
    sys.exit("no hfrag vertex array found")


def read_hfrag(path):
    raw = Path(path).read_bytes()
    data = compression.zstd.decompress(raw[8:])
    offset = find_vertices(data)
    count = struct.unpack_from("<Q", data, offset)[0]
    heights, colors = [0.0] * (EDGE * EDGE), [0] * (EDGE * EDGE)
    for k in range(count):
        height, vi, color, _u, _v, _pad = struct.unpack_from("<fIHBBI", data, offset + 8 + k * 16)
        heights[vi], colors[vi] = height / UNITS, color
    offset += 8 + count * 16
    offset += 8 + struct.unpack_from("<Q", data, offset)[0] * 4      # indices (u32)
    offset += 8 + struct.unpack_from("<Q", data, offset)[0] * 32     # corners (bsphere + 4 u32)
    buckets = struct.unpack_from("<Q", data, offset)[0]
    offset += 8
    for _ in range(buckets):                                         # corner list + u16[16] montage
        offset += 8 + struct.unpack_from("<Q", data, offset)[0] * 4 + 32
    size = struct.unpack_from("<Q", data, offset)[0]                 # PackedTimeOfDay bytes
    offset += 8
    palettes = data[offset : offset + size]
    offset += size
    color_count = struct.unpack_from("<I", data, offset)[0]
    assert size == color_count * 32, "unexpected time-of-day layout"
    # Daylight shade per color (gray, 128 = full).
    shade = [sum(palettes[c * 32 + p * 4] for p in DAY_PALETTES) / len(DAY_PALETTES) for c in range(color_count)]
    return heights, [shade[c] for c in colors], count


def write_glb(path, gltf, blobs):
    binary = b""
    for blob in blobs:
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(blob)})
        binary += blob + b"\0" * (-len(blob) % 4)
    gltf["buffers"] = [{"byteLength": len(binary)}]
    text = json.dumps(gltf, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as out:
        out.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(text) + 8 + len(binary)))
        out.write(struct.pack("<II", len(text), 0x4E4F534A) + text)
        out.write(struct.pack("<II", len(binary), 0x004E4942) + binary)


def grid_mesh(heights, step):
    """Positions and triangle indices of the field, every step-th vertex."""
    side = (EDGE - 1) // step + 1
    positions, indices = [], []
    for gz in range(side):
        for gx in range(side):
            vx, vz = gx * step, gz * step
            positions += [vx * SPACING, heights[vz * EDGE + vx], vz * SPACING]
    for gz in range(side - 1):
        for gx in range(side - 1):
            a = gz * side + gx
            b, c, d = a + 1, a + side, a + side + 1
            # Counter-clockwise seen from above (+Y).
            indices += [a, c, d, a, d, b]
    return side, positions, indices


def main():
    args = sys.argv[1:]
    # --sand TILE.png [--sand-quads N]: a seamless picture (e.g. the Tripo sand, made to tile by
    # tools/blender/make_tileable.py) instead of the composed Wang tiles, repeating every N quads.
    sand_tile, repeat = None, TILE_QUADS
    if "--sand" in args:
        i = args.index("--sand")
        sand_tile = args[i + 1]
        del args[i:i + 2]
    if "--sand-quads" in args:
        i = args.index("--sand-quads")
        repeat = int(args[i + 1])
        del args[i:i + 2]
    if len(args) != 5:
        sys.exit(__doc__)
    fr3, wang, mip, out, collision_out = args
    heights, shades, count = read_hfrag(fr3)

    # Sand: the atlas brought to its mip's color (the PS2 drew the field at double brightness).
    width, height, atlas = read_png(sand_tile or wang)
    _, _, mip_pixels = read_png(mip)
    atlas_mean = [sum(atlas[i::4]) / (width * height) for i in range(3)]
    mip_mean = [sum(mip_pixels[i::4]) / (len(mip_pixels) // 4) for i in range(3)]
    gain = [m / a for m, a in zip(mip_mean, atlas_mean)]
    if sand_tile:
        sand = bytearray(atlas)
    else:
        width, sand = wang_compose(width, atlas)
        sand = quilt(width, sand)
    height = width
    for i in range(0, len(sand), 4):
        for ch in range(3):
            sand[i + ch] = min(255, round(sand[i + ch] * gain[ch]))
        sand[i + 3] = 128  # PS2 alpha: 0x80 is opaque, like the ripped textures

    side, positions, indices = grid_mesh(heights, 1)
    normals, uvs, colors = [], [], []
    for gz in range(side):
        for gx in range(side):
            h = lambda x, z: heights[min(max(z, 0), EDGE - 1) * EDGE + min(max(x, 0), EDGE - 1)]
            nx = (h(gx - 1, gz) - h(gx + 1, gz)) / (2 * SPACING)
            nz = (h(gx, gz - 1) - h(gx, gz + 1)) / (2 * SPACING)
            length = math.sqrt(nx * nx + 1 + nz * nz)
            normals += [nx / length, 1 / length, nz / length]
            uvs += [gx / repeat, gz / repeat]
            shade = shades[gz * EDGE + gx] / 255.0
            colors += [shade, shade, shade, 1.0]
    vertex_count = side * side
    lo = [min(positions[i::3]) for i in range(3)]
    hi = [max(positions[i::3]) for i in range(3)]
    gltf = {
        "asset": {"version": "2.0", "generator": "jak3-ue5 hfrag_to_glb.py"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "desert-hfrag", "mesh": 0}],
        "images": [{"name": "des-hfrag-sand", "bufferView": 5, "mimeType": "image/png"}],
        "samplers": [{"wrapS": 10497, "wrapT": 10497}],
        "textures": [{"name": "des-hfrag-sand", "source": 0, "sampler": 0}],
        "materials": [{"name": "des-hfrag-sand", "pbrMetallicRoughness": {
            "baseColorTexture": {"index": 0}, "baseColorFactor": [2.0, 2.0, 2.0, 2.0]}}],
        "meshes": [{"name": "desert-hfrag", "primitives": [{"attributes": {
            "POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2, "COLOR_0": 3}, "indices": 4, "material": 0}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": vertex_count, "type": "VEC3", "min": lo, "max": hi},
            {"bufferView": 1, "componentType": 5126, "count": vertex_count, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": vertex_count, "type": "VEC2"},
            {"bufferView": 3, "componentType": 5126, "count": vertex_count, "type": "VEC4"},
            {"bufferView": 4, "componentType": 5125, "count": len(indices), "type": "SCALAR"},
        ],
        "bufferViews": [],
    }
    write_glb(Path(out), gltf, [
        struct.pack(f"<{len(positions)}f", *positions), struct.pack(f"<{len(normals)}f", *normals),
        struct.pack(f"<{len(uvs)}f", *uvs), struct.pack(f"<{len(colors)}f", *colors),
        struct.pack(f"<{len(indices)}I", *indices), png_bytes(width, height, sand)])
    print(f"{out}: {count} hfrag vertices, {len(indices) // 3} triangles, heights {lo[1]:.1f}..{hi[1]:.1f} m, "
          f"sand gain {[round(g, 2) for g in gain]}")

    side, positions, indices = grid_mesh(heights, 2)
    lo = [min(positions[i::3]) for i in range(3)]
    hi = [max(positions[i::3]) for i in range(3)]
    write_glb(Path(collision_out), {
        "asset": {"version": "2.0", "generator": "jak3-ue5 hfrag_to_glb.py"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "desert-hfrag-collision", "mesh": 0}],
        "meshes": [{"name": "desert-hfrag-collision", "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": side * side, "type": "VEC3", "min": lo, "max": hi},
            {"bufferView": 1, "componentType": 5125, "count": len(indices), "type": "SCALAR"},
        ],
        "bufferViews": [],
    }, [struct.pack(f"<{len(positions)}f", *positions), struct.pack(f"<{len(indices)}I", *indices)])
    print(f"{collision_out}: {len(indices) // 3} triangles")


if __name__ == "__main__":
    main()
