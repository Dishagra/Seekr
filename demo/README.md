# The demo film

`seekr-demo.mp4` — 81 seconds, 1080p, no audio. Everything on screen is the
real product against the real graph; there are no mockups and no staged data.

## Rebuilding it

```bash
python -m rip.cli serve                 # the app must be running
python demo/film.py                     # records demo/frames/*.png over CDP
ffmpeg -framerate 20 -i demo/frames/f%05d.png \
  -vf "scale=1920:1080:flags=lanczos,format=yuv420p" \
  -c:v libx264 -preset slow -crf 18 -movflags +faststart -r 30 demo/seekr-demo.mp4
```

`film.py` drives headless Chrome over the DevTools protocol and captures at
20fps, so real interface motion is recorded rather than a slideshow of
stills, and re-running it produces the same film.

- `capture.py` — the Chrome/CDP harness
- `scenes.py`  — title cards, lower-third captions, typing, frame recording
- `film.py`    — the running order

Because the graph grows every time it is searched, the people shown will
differ slightly between recordings. That is the product working, not drift.
