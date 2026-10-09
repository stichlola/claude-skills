"""A small Tripo API v3 client (standard library only).

The key is read from the TRIPO_API_KEY environment variable, never printed, and only sent to the
official host. Every paid call checks the balance first; every task is logged (name -> task id, the
prompt, the face limit, the credits) in tasks.json next to the outputs, so a paid task is resumed by
its id instead of being bought again.

    python3 tripo_client.py balance
    python3 tripo_client.py image  <name> "<prompt>"                    # a concept picture (5 credits)
    python3 tripo_client.py text3d <name> "<prompt>" --faces 800        # text -> 3D, textured (~40)
    python3 tripo_client.py image3d <name> --from-image <name> --faces 10000 --pbr   # chosen picture -> 3D (~50)
    python3 tripo_client.py p1 <name> picture.png --faces 1200 [--texture]  # P1 low-poly from a file (+ texture)
    python3 tripo_client.py resume <name> <step>                         # download a finished task again

Options: --out DIR (default ./tripo_out), --max-cost N (stop if the balance is lower, warn if a task
cost more), --negative "<text>".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = "https://openapi.tripo3d.ai/v3"
MODEL_VERSION = "v3.1-20260211"
P1 = "P1-20260311"
TEXTURE_MODEL = "v3.0-20250812"


def key() -> str:
    k = os.environ.get("TRIPO_API_KEY")
    if not k:
        sys.exit("TRIPO_API_KEY is not set")
    return k


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"},
    )
    # Reads retry on a dropped connection; a create does not, so a reset can never pay twice.
    for attempt in range(5 if method == "GET" else 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 401:
                sys.exit("Tripo refused the key (HTTP 401)")
            sys.exit(f"Tripo error HTTP {e.code}: {e.read().decode()[:400]}")
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            if method != "GET" or attempt == 4:
                sys.exit(f"Tripo unreachable: {e}")
            time.sleep(2 ** (attempt + 1))
    if out.get("code") != 0:
        sys.exit(f"Tripo error: {out}")
    return out["data"]


def upload(path: Path) -> str:
    """An image to Tripo's file store; returns its file_token."""
    b = uuid.uuid4().hex
    ctype = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    head = f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: {ctype}\r\n\r\n'
    body = head.encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(
        API + "/files", data=body, method="POST",
        headers={"Authorization": f"Bearer {key()}", "Content-Type": f"multipart/form-data; boundary={b}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    if out.get("code") != 0:
        sys.exit(f"upload failed: {out}")
    return out["data"]["file_token"]


def balance() -> float:
    return float(call("GET", "/account/balance")["balance"])


def wait(task_id: str, timeout: float = 1800) -> dict:
    end, last = time.time() + timeout, None
    while time.time() < end:
        d = call("GET", f"/tasks/{task_id}")
        st = d.get("status")
        if d.get("progress") != last:
            last = d.get("progress")
            print(f"  {task_id[:8]} {st} {last}%", flush=True)
        if st == "success":
            return d
        if st not in ("queued", "running"):
            sys.exit(f"task {task_id} ended {st}: {d.get('error_code')} {d.get('error_message')}")
        time.sleep(4)
    sys.exit(f"task {task_id} timed out: resume it later by its id")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r:  # signed CDN URL, no key sent
        dest.write_bytes(r.read())


class Log:
    def __init__(self, out: Path):
        self.path = out / "tasks.json"

    def read(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def put(self, name: str, step: str, entry: dict) -> None:
        log = self.read()
        log.setdefault(name, {}).setdefault(step, {}).update(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(log, indent=2) + "\n")


def run(log: Log, name: str, step: str, path: str, body: dict, max_cost: float) -> dict:
    """Create one task, wait, log it; warn if it cost more than expected."""
    old = log.read().get(name, {}).get(step)
    if old and old.get("task"):
        print(f"{name} {step}: already paid for (task {old['task'][:8]}), resuming")
        return wait(old["task"])
    bal = balance()
    if bal < max_cost:
        sys.exit(f"balance {bal} is below {max_cost}: stopping")
    print(f"{name} {step}: creating (balance {bal})")
    tid = call("POST", path, body)["task_id"]
    log.put(name, step, {"task": tid, **{k: v for k, v in body.items() if k in ("prompt", "face_limit", "model")}})
    d = wait(tid)
    cost = float(d.get("credits_consumed") or 0)
    log.put(name, step, {"credits": cost})
    print(f"{name} {step}: done, {cost} credits")
    if cost > max_cost:
        print(f"WARNING: {step} cost {cost}, more than {max_cost}")
    return d


def save_outputs(d: dict, out: Path, stem: str) -> None:
    o = d["output"]
    url = o.get("pbr_model_url") or o.get("model_url")
    if url:
        download(url, out / f"{stem}.glb")
    if o.get("generated_image_url"):
        download(o["generated_image_url"], out / f"{stem}.png")
    if o.get("rendered_image_url"):
        download(o["rendered_image_url"], out / f"{stem}.webp")
    print(f"saved {stem} in {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["balance", "image", "text3d", "image3d", "p1", "resume"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("arg", nargs="?", help="prompt, picture file, or step (resume)")
    ap.add_argument("--faces", type=int, default=800)
    ap.add_argument("--pbr", action="store_true")
    ap.add_argument("--texture", action="store_true", help="p1: texture the mesh from the same picture")
    ap.add_argument("--from-image", help="image3d: the name of a picture made with `image`")
    ap.add_argument("--negative", default="realistic, photo, neon, ground plane, base, pedestal, characters, text, multiple objects")
    ap.add_argument("--out", type=Path, default=Path("tripo_out"))
    ap.add_argument("--max-cost", type=float, default=60)
    a = ap.parse_args()
    log = Log(a.out)
    if a.cmd == "balance":
        print(balance())
        return
    if not a.name:
        sys.exit("a name is needed")
    if a.cmd == "image":
        d = run(log, a.name, "image", "/generation/text-to-image", {"prompt": a.arg[:1800]}, a.max_cost)
        save_outputs(d, a.out, f"{a.name}_image")
    elif a.cmd == "text3d":
        body = {
            "prompt": a.arg[:1024], "negative_prompt": a.negative, "model_version": MODEL_VERSION,
            "texture": True, "pbr": a.pbr, "texture_quality": "detailed",
            "smart_low_poly": True, "face_limit": max(500, a.faces),
        }
        save_outputs(run(log, a.name, "model", "/generation/text-to-model", body, a.max_cost), a.out, a.name)
    elif a.cmd == "image3d":
        src = log.read()[a.from_image]["image"]["task"]
        body = {
            "input": src, "model_version": MODEL_VERSION, "texture": True, "pbr": a.pbr,
            "texture_quality": "detailed", "smart_low_poly": True, "face_limit": a.faces,
        }
        save_outputs(run(log, a.name, "model", "/generation/image-to-model", body, a.max_cost), a.out, a.name)
    elif a.cmd == "p1":
        tok = upload(Path(a.arg))
        body = {"input": tok, "model": P1, "face_limit": a.faces, "texture": False, "pbr": False}
        d = run(log, a.name, "mesh", "/generation/image-to-model", body, a.max_cost)
        save_outputs(d, a.out, f"{a.name}_mesh")
        if a.texture:
            mesh = log.read()[a.name]["mesh"]["task"]
            body = {
                "input": mesh, "model": TEXTURE_MODEL, "texture_prompt": {"image": {"file_token": tok}},
                "texture_quality": "detailed", "pbr": True,
            }
            save_outputs(run(log, a.name, "texture", "/models/texture", body, a.max_cost), a.out, a.name)
    elif a.cmd == "resume":
        task = log.read()[a.name][a.arg]["task"]
        save_outputs(wait(task), a.out, f"{a.name}_{a.arg}")
    print(f"balance now {balance()}")


if __name__ == "__main__":
    main()
