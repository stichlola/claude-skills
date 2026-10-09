"""Decode Jak 3's streamed music (and other streams OpenGOAL's ripper skips) to .wav.

    python tools/audio/vagwad_music.py ISO_DIR OUT_DIR NAME [NAME...]   e.g. DESERT WASCITY DESHOVER
    python tools/audio/vagwad_music.py ISO_DIR --list                  names missing from the rip

VAG/VAGDIR.AYB ("VGWADDIR", version 2) lists 64-bit entries: the name in the low 42 bits (two
halves of 4 characters, base 38: " A-Z0-9-"), 6 flag bits, and the offset in 32 KiB blocks in
the top 16 bits. Music lives in VAG/VAGWAD.INT as PS-ADPCM, the two channels interleaved in
0x2000 byte blocks, each channel's first block opening with a "VAGp" header (little-endian
data size and sample rate, "Stereo").
"""

import struct
import sys
import wave
from pathlib import Path

ALPHABET = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
BLOCK = 0x8000
INTERLEAVE = 0x2000
FILTERS = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]


def name_of(entry):
    def half(v):
        out = []
        for _ in range(4):
            out.append(ALPHABET[v % 38])
            v //= 38
        return "".join(reversed(out))
    return (half((entry >> 21) & 0x1FFFFF) + half(entry & 0x1FFFFF)).strip()


def directory(iso):
    data = (Path(iso) / "VAG" / "VAGDIR.AYB").read_bytes()
    count = struct.unpack_from("<I", data, 12)[0]
    entries = [struct.unpack_from("<Q", data, 16 + i * 8)[0] for i in range(count)]
    return {name_of(e): e for e in entries}


def decode_adpcm(data, state):
    """PS-ADPCM frames (16 bytes -> 28 samples); state = [s1, s2] carried across calls."""
    out = []
    s1, s2 = state
    for f in range(0, len(data) - 15, 16):
        shift = data[f] & 0x0F
        predictor = min(data[f] >> 4, 4)
        flags = data[f + 1]
        k1, k2 = FILTERS[predictor]
        for i in range(28):
            byte = data[f + 2 + i // 2]
            nibble = (byte >> 4) if i & 1 else (byte & 0x0F)
            if nibble >= 8:
                nibble -= 16
            sample = (nibble << 12) >> shift
            sample += (s1 * k1 + s2 * k2) >> 6
            sample = max(-32768, min(32767, sample))
            out.append(sample)
            s2, s1 = s1, sample
        if flags == 7:  # end of stream
            break
    state[0], state[1] = s1, s2
    return out


def extract(iso, entry, dest, interleave=INTERLEAVE):
    with open(Path(iso) / "VAG" / "VAGWAD.INT", "rb") as wad:
        wad.seek((entry >> 48) * BLOCK)
        header = wad.read(0x30)
        if header[:4] != b"pGAV":
            raise ValueError(f"no VAGp header ({header[:4]})")
        size, rate = struct.unpack_from("<I", header, 12)[0], struct.unpack_from("<I", header, 16)[0]
        stereo = b"Stereo" in header
        channels = 2 if stereo else 1
        wad.seek((entry >> 48) * BLOCK)
        body = wad.read(size * channels + 0x30 * channels)
    # Blocks of INTERLEAVE bytes alternate between the channels; each channel's first block
    # starts with its own 0x30 byte VAGp header.
    states = [[0, 0] for _ in range(channels)]
    pcm = [[] for _ in range(channels)]
    step = interleave * channels
    for start in range(0, len(body), step):
        for c in range(channels):
            chunk = body[start + c * interleave:start + (c + 1) * interleave]
            if start == 0:
                chunk = chunk[0x30:]
            pcm[c] += decode_adpcm(chunk, states[c])
    frames = min(len(p) for p in pcm)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        samples = [pcm[c][i] for i in range(frames) for c in range(channels)]
        out.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return frames / rate, rate, channels


def main():
    iso = sys.argv[1]
    entries = directory(iso)
    if sys.argv[2] == "--list":
        print(" ".join(sorted(n for n, e in entries.items() if (e >> 42) & 0x3F == 0b100011)))
        return
    out = Path(sys.argv[2])
    for name in sys.argv[3:]:
        seconds, rate, channels = extract(iso, entries[name], out / f"{name.lower()}.wav")
        print(f"{name}: {seconds:.0f} s, {rate} Hz, {channels} ch -> {out / (name.lower() + '.wav')}")


if __name__ == "__main__":
    main()
