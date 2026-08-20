"""Record the Seekr demo film."""
from __future__ import annotations

import pathlib
import re
import shutil
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from capture import Chrome, UI, TOKEN, OUT           # noqa: E402
import scenes                                         # noqa: E402
from scenes import card, caption, caption_off, goto_ui, record, type_query  # noqa: E402

MARK = re.search(r'd="([^"]+)"',
                 (pathlib.Path(__file__).parents[1] / "frontend/assets/mark.svg").read_text()).group(1)
MARK_SVG = (f'<svg viewBox="0 0 512 512" width="620"><path d="{MARK}" '
            'fill="currentColor" fill-rule="evenodd"/></svg>')


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    c = Chrome()
    try:
        # sign in once; the rest of the film is the real product
        c.send("Page.navigate", url=UI)
        time.sleep(2.5)
        c.js(f'localStorage.setItem("seekr_token","{TOKEN}");'
             'localStorage.setItem("seekr_theme","light");'
             'localStorage.removeItem("seekr_recent")')

        # ---- 1. open ----
        card(c, "Seekr", "An evidence-backed people graph.", kicker="Deccan AI",
             seconds=2.8, size=76, mark_svg=MARK_SVG)
        card(c, "Finding the right person is a data problem<br>before it is a ranking problem.",
             sub="Seekr collects, resolves and maintains public profiles. "
                 "It deliberately does not rank them.",
             kicker="The premise", seconds=4.0, size=38, mark_svg=MARK_SVG)

        # ---- 2. ask in plain language ----
        goto_ui(c)
        caption(c, "Ask", "Plain language, against 50,000 people",
                "No query syntax to learn. The corpus grows every time it is searched.")
        record(c, 1.6)
        type_query(c, "machine learning researchers in India")
        record(c, 0.6)
        c.js("runQuery()")
        record(c, 3.4)
        caption_off(c)
        record(c, 0.5)

        # ---- 3. it says what it did ----
        caption(c, "Honesty", "It reports what it actually searched for",
                "Applied filters are shown. Terms the corpus cannot support are "
                "named as dropped rather than quietly ignored.")
        record(c, 3.6)
        caption_off(c)

        # a typo, corrected out loud
        type_query(c, "pythonn developers in bangalor")
        c.js("runQuery()")
        record(c, 1.2)
        caption(c, "Honesty", "Corrections are never silent",
                "A misspelling is fixed against the corpus vocabulary, and the "
                "answer says so.")
        record(c, 3.4)
        caption_off(c)
        record(c, 0.4)
        # ---- 4. every claim carries a source ----
        card(c, "Every claim carries its source.",
             sub="A profile is not a record we assert. It is evidence we collected, "
                 "each piece pointing back at where it came from.",
             kicker="Provenance", seconds=3.6, size=40, mark_svg=MARK_SVG)
        goto_ui(c)
        c.js('document.querySelector("#q").value="geoffrey hinton"; runQuery()')
        time.sleep(3.0)
        record(c, 1.0)
        c.js('document.querySelector("table.list tbody tr").click()')
        time.sleep(3.2)
        caption(c, "Provenance", "One person, assembled from many sources",
                "Publications, affiliations, identifiers and links — each with the "
                "source and the date it was seen.")
        record(c, 3.0)
        for _ in range(3):
            c.js("window.scrollBy({top:520, behavior:'smooth'})")
            record(c, 1.5)
        caption_off(c)
        record(c, 0.4)

        # ---- 5. the graph grows as you search ----
        card(c, "The graph grows every time you search.",
             sub="A question the corpus cannot answer is sent to live sources. "
                 "What comes back is resolved, stored, and free to ask again.",
             kicker="Discovery", seconds=3.8, size=40, mark_svg=MARK_SVG)
        goto_ui(c)
        caption(c, "Discovery", "Asked live, then kept",
                "Ten people found live, resolved against the existing graph, and kept.")
        type_query(c, "rust developers in berlin")
        c.js("runQuery('true')")
        record(c, 7.0)
        caption_off(c)
        record(c, 0.5)

        # ---- 6. filters that mean what they say ----
        card(c, "Filters that mean what they say.",
             sub="Whole-word matching, and an empty result that tells you which "
                 "constraint to relax.",
             kicker="Precision", seconds=3.4, size=40, mark_svg=MARK_SVG)
        goto_ui(c)
        c.js('document.querySelector("#filterbox").open=true')
        record(c, 1.0)
        c.js('document.querySelector("#f_skill").value="go";'
             'document.querySelector("#f_country").value="IN"; runFilters()')
        record(c, 3.0)
        caption(c, "Precision", "skill=go means the language, not the letters",
                "Substring matching returned 1,562 people including Geoffrey Hinton, "
                "through the word Cognitive.")
        record(c, 3.0)
        caption_off(c)
        c.js('document.querySelector("#f_country").value="DE"; runFilters()')
        record(c, 2.4)
        caption(c, "Precision", "An empty answer explains itself",
                "Each filter is measured alone and dropped in turn, so you know "
                "which one to relax.")
        record(c, 3.4)
        caption_off(c)
        record(c, 0.4)

        # ---- 7. a data layer, not a ranking engine ----
        card(c, "A data layer, not a ranking engine.",
             sub="Seekr answers what is true about people and where it learned it. "
                 "Your own tools decide who matters.",
             kicker="Integration", seconds=3.8, size=40, mark_svg=MARK_SVG)
        c.send("Page.navigate", url="http://127.0.0.1:8000/docs")
        time.sleep(3.4)
        caption(c, "Integration", "A read API, an outbox and a change feed",
                "Faceted search, per-person evidence and provenance, an integer "
                "cursor over every change, and signed webhooks.")
        record(c, 2.6)
        for _ in range(2):
            c.js("window.scrollBy({top:560, behavior:'smooth'})")
            record(c, 1.6)
        caption_off(c)
        record(c, 0.4)

        # ---- 8. close ----
        card(c, "Seekr", "Evidence in. Structure out. Ranking stays yours.",
             kicker="Deccan AI", seconds=4.2, size=76, mark_svg=MARK_SVG)
        print(f"[film] captured {scenes.frame_no} frames")
    finally:
        c.close()


if __name__ == "__main__":
    main()
