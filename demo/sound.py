"""Score the film with ffmpeg — there is no sample library here, so every
sound is synthesised.

A quiet held chord underneath, a low swell at each section card, and soft
key ticks while text is typed. Nothing melodic: the picture is doing the
talking and the sound is there to stop the silence feeling like a fault.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
AUDIO = HERE / "audio"
AUDIO.mkdir(exist_ok=True)

# A minor 9th, spelled low and wide. Quiet, slightly detuned so it breathes.
CHORD = [55.00, 110.00, 164.81, 220.00, 246.94, 329.63]
DETUNE = [0, 0.6, -0.5, 0.4, -0.3, 0.5]


def run(args: list[str]):
    subprocess.run(args, check=True, capture_output=True)


def pad(seconds: float, out: pathlib.Path):
    """The bed: detuned sines, filtered dark, with a long reverb tail."""
    inputs, mix = [], []
    for i, (f, d) in enumerate(zip(CHORD, DETUNE)):
        inputs += ["-f", "lavfi", "-t", f"{seconds}",
                   "-i", f"sine=frequency={f + d}:sample_rate=48000"]
        # Each voice drifts on its own slow cycle. Written as a volume
        # expression because tremolo will not go below 0.1Hz, and the movement
        # wanted here is slower than that — closer to breathing than vibrato.
        rate = 0.021 + i * 0.007
        phase = i * 1.1
        mix.append(
            f"[{i}:a]volume='0.16*(0.62+0.38*sin(2*PI*{rate:.4f}*t+{phase:.2f}))'"
            f":eval=frame[v{i}]"
        )
    chain = ";".join(mix)
    chain += ";" + "".join(f"[v{i}]" for i in range(len(CHORD)))
    chain += f"amix=inputs={len(CHORD)}:normalize=0,"
    chain += ("lowpass=f=520,highpass=f=45,"
              "aecho=0.8:0.9:600|1100|1700:0.35|0.24|0.16,"
              "lowpass=f=900,"
              f"afade=t=in:st=0:d=3,afade=t=out:st={seconds - 4:.2f}:d=4,"
              "volume=0.42[out]")
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", chain, "-map", "[out]", "-ac", "2", str(out)])


def swell(out: pathlib.Path):
    """A low, soft rise for a section card."""
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-t", "1.6", "-i", "anoisesrc=color=brown:sample_rate=48000",
         "-af", ("lowpass=f=260,volume=0.9,"
                 "afade=t=in:st=0:d=1.1,afade=t=out:st=1.1:d=0.5,"
                 "aecho=0.8:0.85:420:0.3,volume=0.5"),
         "-ac", "2", str(out)])


def tick(out: pathlib.Path):
    """A key press: a very short filtered click, not a beep."""
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-t", "0.045", "-i", "anoisesrc=color=white:sample_rate=48000",
         "-af", ("highpass=f=1400,lowpass=f=5200,"
                 "afade=t=out:st=0.004:d=0.04,volume=0.16"),
         "-ac", "2", str(out)])


def chime(out: pathlib.Path):
    """Results landing: two soft partials, quickly gone."""
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-t", "1.2", "-i", "sine=frequency=659.25:sample_rate=48000",
         "-f", "lavfi", "-t", "1.2", "-i", "sine=frequency=987.77:sample_rate=48000",
         "-filter_complex",
         ("[0:a]volume=0.5[a];[1:a]volume=0.3[b];[a][b]amix=inputs=2:normalize=0,"
          "afade=t=out:st=0.05:d=1.0,aecho=0.8:0.88:320:0.28,volume=0.30[out]"),
         "-map", "[out]", "-ac", "2", str(out)])


if __name__ == "__main__":
    manifest = json.loads((HERE / "marks.json").read_text())
    seconds = manifest["frames"] / manifest["fps"]
    pad(seconds, AUDIO / "pad.wav")
    swell(AUDIO / "swell.wav")
    tick(AUDIO / "tick.wav")
    chime(AUDIO / "chime.wav")
    print(f"pad {seconds:.1f}s, swell, tick, chime written")
