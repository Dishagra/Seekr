"""Record the Seekr demo film.

Everything on screen is the real product against the real graph. Scene
boundaries are written to marks.json so the edit can zoom, and so the sound
can be cut to the picture.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from capture import Chrome, UI, TOKEN, OUT                      # noqa: E402
import scenes                                                    # noqa: E402
from scenes import (MARKS, card, caption, caption_corrected,      # noqa: E402
                    caption_counted, caption_off, caption_typed,
                    goto_ui, mark, record, type_query)

MARK = re.search(r'd="([^"]+)"',
                 (pathlib.Path(__file__).parents[1] / "frontend/assets/mark.svg").read_text()).group(1)
MARK_SVG = (f'<svg viewBox="0 0 512 512" width="620"><path d="{MARK}" '
            'fill="currentColor" fill-rule="evenodd"/></svg>')


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    c = Chrome()
    try:
        c.send("Page.navigate", url=UI)
        time.sleep(2.5)
        c.js(f'localStorage.setItem("seekr_token","{TOKEN}");'
             'localStorage.setItem("seekr_theme","light");'
             'localStorage.removeItem("seekr_recent")')

        # ---- open ----
        mark("title", "card")
        card(c, "Seekr", "Public evidence about people, collected and kept current.",
             kicker="Deccan AI", seconds=2.9, size=76, mark_svg=MARK_SVG)
        mark("premise", "card")
        card(c, "Fifty thousand people.<br>Every claim traceable to its source.",
             sub="Seekr discovers public profiles, resolves them into one person, "
                 "and maintains them as the sources change.",
             kicker="What it is", seconds=4.0, size=38, mark_svg=MARK_SVG)

        # ---- ask, zoomed on the search field ----
        goto_ui(c)
        mark("ask", "zoom_search")
        caption_typed(c, "Ask", "Plain language. No query syntax.",
                      "Fifty thousand people, searched the way you would describe them.")
        record(c, 0.8)
        type_query(c, "machine learning researchers in India")
        record(c, 0.5)
        c.js("runQuery()")
        record(c, 3.2)
        caption_off(c)
        record(c, 0.4)

        # ---- any field, not just software ----
        mark("breadth_card", "card")
        card(c, "The same question, in any field.",
             sub="The vocabulary comes from the corpus itself, so a question about "
                 "climate modelling parses exactly like one about compilers.",
             kicker="Breadth", seconds=3.4, size=40, mark_svg=MARK_SVG)
        goto_ui(c)
        mark("breadth_climate", "zoom_search")
        type_query(c, "climate model intercomparison researchers")
        c.js("runQuery('true')")
        record(c, 3.0)
        c.js("window.scrollBy({top:190, behavior:'smooth'})")
        record(c, 0.9)
        caption(c, "Breadth", "Climate science",
                "Veronika Eyring, Ronald Stouffer, Gerald Meehl, Karl Taylor — the "
                "people who lead the model intercomparison projects.")
        record(c, 3.2)
        caption_off(c)
        record(c, 0.3)
        mark("breadth_bio")
        type_query(c, "structural biologists working on protein folding")
        c.js("runQuery('true')")
        record(c, 3.0)
        c.js("window.scrollBy({top:190, behavior:'smooth'})")
        record(c, 0.9)
        caption(c, "Breadth", "Structural biology",
                "Martin Karplus, who shared the Nobel Prize for exactly this.")
        record(c, 3.2)
        caption_off(c)
        record(c, 0.4)

        # ---- corrections ----
        mark("correction", "zoom_search")
        type_query(c, "pythonn developers in bangalor")
        c.js("runQuery()")
        record(c, 1.2)
        caption_corrected(c, "Understanding", "pythonn developers in bangalor",
                          "python · Bangalore",
                          "Spelling is corrected against the corpus, and the answer "
                          "says what it searched for.")
        record(c, 1.4)
        caption_off(c)
        record(c, 0.4)
        print(f"[film] act one: {scenes.frame_no}")
        _act_two(c)
    finally:
        pathlib.Path(__file__).parent.joinpath("marks.json").write_text(
            json.dumps({"fps": scenes.FPS, "frames": scenes.frame_no, "marks": MARKS}, indent=1))
        c.close()


def _act_two(c: Chrome):
    """Provenance, the pipelines behind it, discovery, shortlists and the API."""
    # ---- provenance ----
    mark("provenance_card", "card")
    card(c, "Every claim points back at where it came from.",
         sub="A profile is not something we assert. It is evidence we collected, "
             "each piece carrying its source and the date it was seen.",
         kicker="Provenance", seconds=3.6, size=40, mark_svg=MARK_SVG)
    goto_ui(c)
    mark("provenance_person")
    c.js('document.querySelector("#q").value="geoffrey hinton"; runQuery()')
    time.sleep(3.0)
    record(c, 0.8)
    c.js('document.querySelector("table.list tbody tr").click()')
    time.sleep(3.2)
    caption(c, "Provenance", "One person, assembled from many sources",
            "Identifiers, affiliations, publications and links — reconciled into "
            "a single record.")
    record(c, 2.6)
    for _ in range(3):
        c.js("window.scrollBy({top:540, behavior:'smooth'})")
        record(c, 1.4)
    caption_off(c)
    record(c, 0.3)

    # ---- the pipelines ----
    mark("pipelines_card", "card")
    card(c, "Nine sources, one pipeline.",
         sub="Each connector normalises into the same shape, then resolution "
             "decides whether it is a new person or more evidence about a known one.",
         kicker="Pipelines", seconds=3.6, size=40, mark_svg=MARK_SVG)
    mark("pipelines")
    c.send("Page.navigate", url=UI + "#/sources")
    time.sleep(3.0)
    caption(c, "Pipelines", "Every source, and what it has contributed",
            "Records ingested, when each was last refreshed, and what it is "
            "permitted to fetch.")
    record(c, 3.6)
    c.js("window.scrollBy({top:420, behavior:'smooth'})")
    record(c, 1.8)
    caption_off(c)
    record(c, 0.3)

    # ---- resolution review ----
    mark("review")
    c.send("Page.navigate", url=UI + "#/review")
    time.sleep(3.0)
    caption(c, "Pipelines", "Uncertain merges are held for review",
            "Two records that might be one person are queued rather than merged "
            "silently, and either decision is reversible.")
    record(c, 3.8)
    caption_off(c)
    record(c, 0.3)

    # ---- discovery ----
    mark("discovery_card", "card")
    card(c, "The graph grows every time you search.",
         sub="A question the corpus cannot answer fully is put to live sources. "
             "What comes back is resolved, stored, and free to ask again.",
         kicker="Discovery", seconds=3.6, size=40, mark_svg=MARK_SVG)
    goto_ui(c)
    mark("discovery", "zoom_search")
    type_query(c, "rust developers in berlin")
    c.js("runQuery('true')")
    record(c, 5.0)
    caption_counted(c, "Discovery", "{n} new people, resolved and kept", 10,
                    "Found live, matched against everyone already in the graph, "
                    "then written in.")
    record(c, 1.6)
    caption_off(c)
    record(c, 0.4)

    # ---- shortlists ----
    mark("shortlist_card", "card")
    card(c, "Keep the people worth keeping.",
         sub="Save anyone into a named list. Each entry remembers the query that "
             "found them, so the reason survives.",
         kicker="Shortlists", seconds=3.4, size=40, mark_svg=MARK_SVG)
    goto_ui(c)
    mark("shortlist_save")
    c.js('document.querySelector("#q").value="rust developers in berlin"; runQuery()')
    time.sleep(3.2)
    caption(c, "Shortlists", "Save someone in one click", "")
    record(c, 1.2)
    c.js("""(function(){
      window.prompt = () => "Rust · Berlin";
      const b=[...document.querySelectorAll('button')].filter(x=>x.title==='Save to a shortlist');
      b[0] && b[0].click(); setTimeout(()=>b[2] && b[2].click(), 700);
      setTimeout(()=>b[4] && b[4].click(), 1400);
    })()""")
    record(c, 3.2)
    caption_off(c)
    mark("shortlist_page")
    c.send("Page.navigate", url=UI + "#/shortlists")
    time.sleep(2.8)
    caption(c, "Shortlists", "And the query that found them",
            "Months later, the list still says why each person is on it.")
    record(c, 3.6)
    caption_off(c)
    record(c, 0.3)

    # ---- the API ----
    mark("api_card", "card")
    card(c, "Everything you have seen, over HTTP.",
         sub="Faceted search, per-person evidence and provenance, an integer "
             "cursor over every change, and signed webhooks.",
         kicker="Integration", seconds=3.6, size=40, mark_svg=MARK_SVG)
    mark("api")
    c.send("Page.navigate", url="http://127.0.0.1:8000/docs")
    time.sleep(3.4)
    caption(c, "Integration", "A read API your own systems can build on", "")
    record(c, 2.4)
    for _ in range(2):
        c.js("window.scrollBy({top:560, behavior:'smooth'})")
        record(c, 1.5)
    caption_off(c)
    record(c, 0.4)

    # ---- close ----
    mark("close", "card")
    card(c, "Seekr", "Evidence in. Structure out.", kicker="Deccan AI",
         seconds=4.0, size=76, mark_svg=MARK_SVG)
    print(f"[film] captured {scenes.frame_no} frames")


if __name__ == "__main__":
    main()
