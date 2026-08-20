"""Edit the recording into one continuous piece.

Three things happen here. Frames are timed by when they were actually
captured, not by a nominal rate — screenshot latency varies by tens of
milliseconds, and pretending otherwise is what makes UI footage judder.
Scene changes are cross-dissolved rather than cut. And the search field is
pushed into while a query is typed.
"""
from __future__ import annotations

import json
import pathlib
import shutil

from PIL import Image

HERE = pathlib.Path(__file__).parent
FRAMES = HERE / "frames"
EDIT = HERE / "edit"

W, H = 1600, 900
SEARCH_CENTRE = (860, 150)
ZOOM = 1.26
DISSOLVE = 9            # frames of cross-fade at a scene change


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def zoom_curve(i: int, n: int) -> float:
    a, b, c_, d = 0.03, 0.24, 0.48, 0.66
    p = i / max(1, n - 1)
    if p <= a:
        return 0.0
    if p < b:
        return ease((p - a) / (b - a))
    if p < c_:
        return 1.0
    if p < d:
        return 1.0 - ease((p - c_) / (d - c_))
    return 0.0


def crop_for(amount: float):
    z = 1 + (ZOOM - 1) * amount
    cw, ch = W / z, H / z
    cx, cy = SEARCH_CENTRE
    left = min(max(cx - cw / 2, 0), W - cw)
    top = min(max(cy - ch / 2, 0), H - ch)
    return int(left), int(top), int(left + cw), int(top + ch)


def main():
    manifest = json.loads((HERE / "marks.json").read_text())
    marks, total = manifest["marks"], manifest["frames"]
    stamps = manifest.get("stamps") or []

    spans = []
    for i, m in enumerate(marks):
        end = marks[i + 1]["start"] - 1 if i + 1 < len(marks) else total
        spans.append((m["start"], end, m["kind"]))

    shutil.rmtree(EDIT, ignore_errors=True)
    EDIT.mkdir()

    # pass one: the push-in
    for start, end, kind in spans:
        n = end - start + 1
        for k, f in enumerate(range(start, end + 1)):
            src, dst = FRAMES / f"f{f:05d}.png", EDIT / f"e{f:05d}.png"
            amount = zoom_curve(k, n) if kind == "zoom_search" else 0.0
            if amount <= 0.001:
                shutil.copyfile(src, dst)
            else:
                Image.open(src).crop(crop_for(amount)).resize((W, H), Image.LANCZOS).save(dst)

    # pass two: dissolve across every scene change, so nothing ever cuts
    for start, _end, _kind in spans[1:]:
        first = EDIT / f"e{start:05d}.png"
        if not first.exists():
            continue
        incoming = Image.open(first).convert("RGB")
        for j in range(DISSOLVE):
            f = start - DISSOLVE + j
            path = EDIT / f"e{f:05d}.png"
            if f < 1 or not path.exists():
                continue
            outgoing = Image.open(path).convert("RGB")
            Image.blend(outgoing, incoming, ease((j + 1) / (DISSOLVE + 1))).save(path)

    # pass three: hold each frame for exactly as long as it was on screen
    lines = ["ffconcat version 1.0"]
    default = 1 / manifest["fps"]
    for i, f in enumerate(range(1, total + 1)):
        if stamps and i + 1 < len(stamps):
            dur = max(0.012, min(0.075, stamps[i + 1] - stamps[i]))
        else:
            dur = default
        lines.append(f"file '{(EDIT / f'e{f:05d}.png').as_posix()}'")
        lines.append(f"duration {dur:.4f}")
    lines.append(f"file '{(EDIT / f'e{total:05d}.png').as_posix()}'")
    (HERE / "sequence.txt").write_text("\n".join(lines))

    # Where each scene lands once the frames are timed — the sound is cut to
    # these, not to the wall clock of the recording, which included the dead
    # time while pages navigated.
    cum, times = 0.0, {}
    starts = {mk["start"]: mk["name"] for mk in marks}
    for i, f in enumerate(range(1, total + 1)):
        if f in starts:
            times[starts[f]] = cum
        if stamps and i + 1 < len(stamps):
            cum += max(0.012, min(0.075, stamps[i + 1] - stamps[i]))
        else:
            cum += default
    (HERE / "cues.json").write_text(json.dumps(
        {"length": cum, "marks": [{"name": mk["name"], "kind": mk["kind"],
                                   "t": times.get(mk["name"], 0.0)} for mk in marks]}, indent=1))
    span = (stamps[-1] - stamps[0]) if len(stamps) > 1 else total / manifest["fps"]
    print(f"edited {total} frames, dissolves at {len(spans)-1} cuts, {span:.1f}s of real time")


if __name__ == "__main__":
    main()
