"""Record the running Seekr UI as a frame sequence, via Chrome DevTools.

Headless Chrome is driven over CDP so the capture is deterministic: the same
script produces the same film every time, and real interface animation is
recorded rather than a slideshow of stills.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.request

import websocket

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9222
W, H = 1600, 900
SCALE = 1                      # 1600x900 native; upscaled at encode time
OUT = pathlib.Path(__file__).parent / "frames"
UI = "http://127.0.0.1:8000/ui"
TOKEN = os.environ["RIP_API_TOKEN"]


class Chrome:
    def __init__(self):
        self.profile = pathlib.Path("/tmp/seekr-demo-profile")
        shutil.rmtree(self.profile, ignore_errors=True)
        self.proc = subprocess.Popen([
            CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
            f"--user-data-dir={self.profile}",
            f"--window-size={W},{H}", f"--force-device-scale-factor={SCALE}",
            "--hide-scrollbars", "--disable-gpu", "--no-first-run",
            "--disable-features=Translate,MediaRouter",
            "--remote-allow-origins=*", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        for _ in range(60):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                page = next(p for p in pages if p["type"] == "page")
                ws_url = page["webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.5)
        if not ws_url:
            raise SystemExit("could not reach Chrome over CDP")
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self.n = 0
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send("Emulation.setDeviceMetricsOverride",
                  width=W, height=H, deviceScaleFactor=SCALE, mobile=False)

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, awaitPromise=True,
                      returnByValue=True)
        return r.get("result", {}).get("value")

    def shot(self, path):
        data = self.send("Page.captureScreenshot", format="png")["data"]
        import base64
        path.write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.ws.close()
        finally:
            self.proc.terminate()
