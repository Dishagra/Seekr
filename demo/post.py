"""Edit the recording: push in on the search field where the film is about
typing, and leave every other scene alone.

The zoom is done on the frames rather than in the encoder so the easing can
be shaped precisely — in as the first character is typed, held while the
query is written, out as the results arrive.
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
SEARCH_CENTRE = (860, 150)     # the search field and the space under it
ZOOM = 1.30                    # gentle: a lean in, not a magnifying glass


def ease(t: float) -> float:
    """Ease in and out — no linear moves, they read as mechanical."""
    return t * t * (3 - 2 * t)


def zoom_curve(i: int, n: int) -> float:
    """0 at the edges, 1 while the typing happens."""
    a, b, c_, d = 0.03, 0.22, 0.46, 0.62      # in-start, in-end, hold-end, out-end
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


def crop_for(amount: float) -> tuple[int, int, int, int]:
    z = 1 + (ZOOM - 1) * amount
    cw, ch = W / z, H / z
    cx, cy = SEARCH_CENTRE
    # keep the window inside the frame
    left = min(max(cx - cw / 2, 0), W - cw)
    top = min(max(cy - ch / 2, 0), H - ch)
    return int(left), int(top), int(left + cw), int(top + ch)


def main():
    manifest = json.loads((HERE / "marks.json").read_text())
    marks = manifest["marks"]
    total = manifest["frames"]
    spans = []
    for i, m in enumerate(marks):
        end = marks[i + 1]["start"] - 1 if i + 1 < len(marks) else total
        spans.append((m["start"], end, m["kind"]))

    shutil.rmtree(EDIT, ignore_errors=True)
    EDIT.mkdir()
    zoomed = 0
    for start, end, kind in spans:
        n = end - start + 1
        for k, f in enumerate(range(start, end + 1)):
            src = FRAMES / f"f{f:05d}.png"
            dst = EDIT / f"e{f:05d}.png"
            amount = zoom_curve(k, n) if kind == "zoom_search" else 0.0
            if amount <= 0.001:
                shutil.copyfile(src, dst)
                continue
            im = Image.open(src)
            im.crop(crop_for(amount)).resize((W, H), Image.LANCZOS).save(dst)
            zoomed += 1
    print(f"edited {total} frames, {zoomed} with a push-in")


if __name__ == "__main__":
    main()
