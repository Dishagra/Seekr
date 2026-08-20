"""Cut the sound to the picture, using the scene marks from the recording."""
from __future__ import annotations

import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
AUDIO = HERE / "audio"


def main():
    m = json.loads((HERE / "marks.json").read_text())
    fps, total = m["fps"], m["frames"]
    marks = m["marks"]
    duration = total / fps

    spans = []
    for i, mk in enumerate(marks):
        end = marks[i + 1]["start"] - 1 if i + 1 < len(marks) else total
        spans.append((mk["start"], end, mk["kind"], mk["name"]))

    cues: list[tuple[str, float]] = []
    for start, end, kind, _name in spans:
        t = start / fps
        if kind == "card":
            cues.append(("swell", t))                     # a section begins
        if kind == "zoom_search":
            # key ticks while the query is typed, then results landing
            for k in range(46):
                cues.append(("tick", t + 1.0 + k * 0.075))
            cues.append(("chime", t + (end - start) / fps * 0.62))

    cues = [(s, t) for s, t in cues if 0 <= t < duration - 0.4]

    inputs = ["-i", str(AUDIO / "pad.wav")]
    files = {"swell": AUDIO / "swell.wav", "tick": AUDIO / "tick.wav",
             "chime": AUDIO / "chime.wav"}
    order = {}
    idx = 1
    for name, path in files.items():
        inputs += ["-i", str(path)]
        order[name] = idx
        idx += 1

    parts, labels = [], ["[0:a]"]
    for n, (sound, t) in enumerate(cues):
        lbl = f"[c{n}]"
        parts.append(f"[{order[sound]}:a]adelay={int(t*1000)}|{int(t*1000)},"
                     f"apad=whole_dur={duration:.2f}{lbl}")
        labels.append(lbl)
    chain = ";".join(parts)
    if parts:
        chain += ";"
    chain += "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
    # Bring the whole mix up to something audible on a laptop speaker — the
    # first cut measured -37dB mean, which is inaudible in a meeting — then
    # hold a ceiling so nothing ever spikes.
    chain += ("volume=13dB,")
    chain += (f"alimiter=limit=0.86,afade=t=in:st=0:d=1.5,"
              f"afade=t=out:st={duration-2.5:.2f}:d=2.4[out]")

    out = AUDIO / "track.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                    "-filter_complex", chain, "-map", "[out]",
                    "-t", f"{duration:.2f}", "-ac", "2", "-ar", "48000", str(out)],
                   check=True)
    print(f"mixed {len(cues)} cues over {duration:.1f}s -> {out.name}")


if __name__ == "__main__":
    main()
