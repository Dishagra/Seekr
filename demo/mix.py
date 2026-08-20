"""Cut the sound to the picture using the scene marks from the recording."""
from __future__ import annotations

import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
AUDIO = HERE / "audio"


TARGET = 58.0        # the film has to land under a minute


def main():
    cues_file = json.loads((HERE / "cues.json").read_text())
    marks = cues_file["marks"]
    speed = max(1.0, cues_file["length"] / TARGET)
    duration = cues_file["length"] / speed

    def at(mark) -> float:
        return mark["t"] / speed

    cues: list[tuple[str, float, float]] = []       # sound, time, gain
    for i, mk in enumerate(marks):
        t = at(mk)
        if i == 0:
            continue                                 # the open has its own chord
        if mk["kind"] == "card":
            cues.append(("whoosh", max(0, t - 0.35), 0.9))
            cues.append(("sub", t, 0.85))
            cues.append(("mark_in", t + 0.04, 0.55))
        else:
            cues.append(("whoosh", max(0, t - 0.25), 0.5))
            cues.append(("mark_soft", t, 0.32))
        if mk["kind"] == "zoom_search":
            cues.append(("land", t + 2.6, 0.42))     # results arriving

    cues.append(("mark_in", 0.25, 0.6))
    if marks:
        cues.append(("close", max(0.0, at(marks[-1]) - 0.2), 0.75))
    cues = [(s, t, g) for s, t, g in cues if 0 <= t < duration - 0.2]

    files = ["bed", "mark_in", "mark_soft", "sub", "whoosh", "land", "close"]
    inputs, idx = [], {}
    for k, name in enumerate(files):
        inputs += ["-i", str(AUDIO / f"{name}.wav")]
        idx[name] = k

    parts, labels = [], ["[0:a]"]
    for n, (sound, t, gain) in enumerate(cues):
        lbl = f"[c{n}]"
        parts.append(f"[{idx[sound]}:a]volume={gain},adelay={int(t*1000)}|{int(t*1000)},"
                     f"apad=whole_dur={duration + 1:.2f}{lbl}")
        labels.append(lbl)

    chain = ";".join(parts) + (";" if parts else "")
    chain += "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
    # a room around everything, so the pieces sit together instead of stacking
    chain += ("aecho=0.85:0.9:280|620:0.22|0.12,"
              "highpass=f=32,lowpass=f=11000,volume=2dB,alimiter=limit=0.72,"
              f"afade=t=in:st=0:d=1.2,afade=t=out:st={max(0.1, duration-2.2):.2f}:d=2.1[out]")

    out = AUDIO / "track.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                    "-filter_complex", chain, "-map", "[out]",
                    "-t", f"{duration:.2f}", "-ac", "2", "-ar", "48000", str(out)], check=True)
    (HERE / "speed.txt").write_text(f"{speed:.5f}")
    print(f"mixed {len(cues)} cues over {duration:.1f}s (picture sped {speed:.3f}x)")


if __name__ == "__main__":
    main()
