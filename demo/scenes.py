"""The demo film: a scripted walkthrough of Seekr, recorded frame by frame.

Everything on screen is the real product against the real graph — no mockups
and no staged data. Re-running this produces the same film.
"""
from __future__ import annotations

import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from capture import Chrome, UI, TOKEN, OUT   # noqa: E402

FPS = 20
frame_no = 0


def frame_path() -> pathlib.Path:
    global frame_no
    frame_no += 1
    return OUT / f"f{frame_no:05d}.png"


def record(c: Chrome, seconds: float):
    """Capture at FPS for a duration, keeping real time as steady as we can."""
    for _ in range(max(1, int(seconds * FPS))):
        t0 = time.time()
        c.shot(frame_path())
        rest = (1 / FPS) - (time.time() - t0)
        if rest > 0:
            time.sleep(rest)


CAPTION_CSS = """
#demo-cap{
  /* starts after the rail, so the navigation and the corpus counts stay
     readable underneath it */
  position:fixed; left:236px; right:0; bottom:0; z-index:9999;
  padding:26px 40px 30px; pointer-events:none;
  background:linear-gradient(180deg, transparent, rgba(17,17,19,.90) 42%);
  color:#F6F3F0; font-family:var(--sans, system-ui);
  opacity:0; transition:opacity .45s cubic-bezier(.22,.61,.36,1);
}
#demo-cap.on{opacity:1}
#demo-cap .k{
  font-size:11px; letter-spacing:.16em; text-transform:uppercase;
  color:#8FB0FF; margin-bottom:7px; font-weight:600;
}
#demo-cap .t{font-size:25px; font-weight:600; letter-spacing:-.02em; line-height:1.25}
#demo-cap .s{font-size:15px; color:#C9C4BE; margin-top:6px; max-width:70ch}
"""


MARKS: list[dict] = []          # scene boundaries, for post-production


def mark(name: str, kind: str = "plain"):
    """Record where a scene starts so the edit can treat it differently."""
    import scenes as _self
    MARKS.append({"name": name, "kind": kind, "start": _self.frame_no + 1})


def caption_typed(c: Chrome, kicker: str, title: str, sub: str = "",
                  per_char: float = 0.022):
    """A caption that types itself — used where the feature is typing."""
    caption(c, kicker, "", sub)
    for i in range(1, len(title) + 1):
        c.js('(document.querySelector("#demo-cap .t")||{}).textContent=%r' % title[:i])
        t0 = time.time()
        c.shot(frame_path())
        rest = per_char - (time.time() - t0)
        if rest > 0:
            time.sleep(rest)


def caption_corrected(c: Chrome, kicker: str, wrong: str, right: str, sub: str = ""):
    """A caption that fixes its own spelling — used for the correction feature."""
    caption(c, kicker, wrong, sub)
    record(c, 0.8)
    c.js("""(function(){
      const t=document.querySelector('#demo-cap .t');
      t.innerHTML=`<s style="opacity:.45;text-decoration-thickness:1px">%s</s>`;
      setTimeout(()=>{ t.innerHTML=`<s style="opacity:.35;text-decoration-thickness:1px">%s</s>`
        + ` <span style="color:#8FB0FF">%s</span>`; }, 380);
    })()""" % (wrong, wrong, right))
    record(c, 1.5)


def caption_counted(c: Chrome, kicker: str, template: str, to: int, sub: str = ""):
    """A caption whose number counts up — used where the graph grows."""
    caption(c, kicker, template.replace("{n}", "0"), sub)
    c.js("""(function(){
      const t=document.querySelector('#demo-cap .t');
      const target=%d, tpl=%r, started=performance.now(), ms=1100;
      (function step(now){
        const p=Math.min(1,(now-started)/ms), e=1-Math.pow(1-p,3);
        t.textContent=tpl.replace('{n}', String(Math.round(target*e)));
        if(p<1) requestAnimationFrame(step);
      })(started);
    })()""" % (to, template))
    record(c, 1.6)


def caption(c: Chrome, kicker: str, title: str, sub: str = ""):
    c.js("""(function(){
      if(!document.getElementById('demo-cap-style')){
        const st=document.createElement('style');
        st.id='demo-cap-style'; st.textContent=%r; document.head.appendChild(st);
      }
      let el=document.getElementById('demo-cap');
      if(!el){ el=document.createElement('div'); el.id='demo-cap'; document.body.appendChild(el); }
      el.innerHTML=`<div class="k">%s</div><div class="t">%s</div>`+(%r?`<div class="s">%s</div>`:``);
      requestAnimationFrame(()=>el.classList.add('on'));
    })()""" % (CAPTION_CSS, kicker, title, sub, sub))


def caption_off(c: Chrome):
    c.js("(document.getElementById('demo-cap')||{classList:{remove(){}}}).classList.remove('on')")


SET_VALUE = """(function(v){
  const el = document.querySelector('input');
  if (!el) return false;
  // React owns the input's value, so assigning to .value is ignored. Go
  // through the native setter and raise the event React actually listens for.
  const set = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value').set;
  set.call(el, v);
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})"""


def submit(c: Chrome):
    """Run the query the way a person would — by pressing Enter."""
    c.js("""(function(){
      const el = document.querySelector('input');
      el && el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
    })()""")


def click_live(c: Chrome):
    c.js("""(function(){
      const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Live');
      b && b.click();
    })()""")


def type_query(c: Chrome, text: str, per_char: float = 0.026):
    """Type into the search box a character at a time, recording as we go."""
    c.js("document.querySelector('input') && document.querySelector('input').focus()")
    for i in range(1, len(text) + 1):
        c.js(f"{SET_VALUE}({text[:i]!r})")
        t0 = time.time()
        c.shot(frame_path())
        rest = per_char - (time.time() - t0)
        if rest > 0:
            time.sleep(rest)


TITLE_CARD = """
<!doctype html><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
 html,body{margin:0;height:100%%;background:%(bg)s;
   font-family:"Instrument Sans",-apple-system,system-ui,sans-serif;color:%(ink)s}
 .wrap{height:100%%;display:grid;place-items:center;text-align:center;position:relative;overflow:hidden}
 .mk{position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%) rotate(-6deg);
   width:620px;color:%(ink)s;opacity:.05}
 .in{position:relative;z-index:2;max-width:60ch;padding:0 40px}
 h1{font-size:%(size)spx;font-weight:600;letter-spacing:-.035em;line-height:1.08;margin:0}
 p{font-size:19px;color:%(muted)s;margin:18px 0 0;line-height:1.5}
 .k{font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:%(accent)s;
   font-weight:600;margin-bottom:20px}
 .rule{width:56px;height:2px;background:%(accent)s;margin:26px auto 0;opacity:.5}
</style>
<div class="wrap">
  <div class="mk">%(mark)s</div>
  <div class="in">
    %(kicker)s<h1>%(title)s</h1>%(sub)s
    <div class="rule"></div>
  </div>
</div>
"""


def card(c: Chrome, title: str, sub: str = "", kicker: str = "", dark: bool = True,
         seconds: float = 2.6, size: int = 54, mark_svg: str = ""):
    import urllib.parse
    html = TITLE_CARD % {
        "bg": "#111113" if dark else "#F6F3F0",
        "ink": "#F6F3F0" if dark else "#111113",
        "muted": "#A9A39D" if dark else "#6D6A66",
        "accent": "#5B8CFF" if dark else "#175FFF",
        "title": title, "size": size,
        "sub": f"<p>{sub}</p>" if sub else "",
        "kicker": f'<div class="k">{kicker}</div>' if kicker else "",
        "mark": mark_svg,
    }
    c.send("Page.navigate", url="data:text/html;charset=utf-8," + urllib.parse.quote(html))
    time.sleep(1.4)
    record(c, seconds)


def goto_ui(c: Chrome, hash_: str = "#/search", settle: float = 2.4):
    c.send("Page.navigate", url=UI + hash_)
    time.sleep(settle)
