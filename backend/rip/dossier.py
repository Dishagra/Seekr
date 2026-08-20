"""A one-person dossier: what Seekr knows, and where each part came from.

The shape follows the recruitment screener's report, because that is what the
work is for — an artifact a human reads before an interview. What it does not
follow is the screener's indirect rubric. Nothing here infers temperament,
character or personality from someone's public behaviour; every line is an
attribute a named source stated, with a link back to the source that stated
it. Judgement is the reader's job.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (Affiliation, Authorship, Evidence, IdentityLink,
                     Organization, Person, Publication, SourceRecord)

MARK = re.search(
    r'd="([^"]+)"',
    (Path(__file__).resolve().parents[2] / "frontend/assets/mark.svg").read_text(),
).group(1) if (Path(__file__).resolve().parents[2] / "frontend/assets/mark.svg").exists() else ""


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def collect(session: Session, person: Person) -> dict:
    """Everything the dossier renders, gathered in one place."""
    evidence = session.execute(
        select(Evidence).where(Evidence.person_id == person.id)
    ).scalars().all()

    sources = sorted({e.source for e in evidence if e.source})
    corroborated = [e for e in evidence if e.verification_state == "corroborated"]

    # How completely do we know this person? The screener reports an evidence
    # coverage figure and it is the most useful number on the page, because it
    # tells the reader how much weight the rest of it can carry.
    dimensions = {
        "identity": bool(person.canonical_name),
        "affiliation": any(e.attribute_type == "affiliation" for e in evidence),
        "role": any(e.attribute_type == "role" for e in evidence),
        "location": bool(person.location or person.country),
        "expertise": any(e.attribute_type in ("skill", "research_interest") for e in evidence),
        "output": session.scalar(
            select(func.count()).select_from(Authorship).where(Authorship.person_id == person.id)
        ) > 0,
        "profiles": bool(person.profile_urls),
        "corroboration": bool(corroborated),
    }
    coverage = round(100 * sum(dimensions.values()) / len(dimensions))

    affiliations = session.execute(
        select(Organization.name, Affiliation.role, Affiliation.relation,
               Affiliation.start_date, Affiliation.end_date)
        .join(Affiliation, Affiliation.organization_id == Organization.id)
        .where(Affiliation.person_id == person.id)
    ).all()

    works = session.execute(
        select(Publication.title, Publication.venue, Publication.published_date,
               Publication.citations, Publication.url)
        .join(Authorship, Authorship.publication_id == Publication.id)
        .where(Authorship.person_id == person.id)
        .order_by(Publication.citations.desc().nullslast())
        .limit(8)
    ).all()

    records = session.execute(
        select(SourceRecord.source, SourceRecord.url, SourceRecord.last_observed)
        .join(IdentityLink, IdentityLink.source_record_id == SourceRecord.id)
        .where(IdentityLink.person_id == person.id)
        .order_by(SourceRecord.last_observed.desc())
    ).all()

    # The strongest evidence: claims more than one source agrees on, then the
    # rest by confidence. Same idea as the screener's evidence table.
    ranked = sorted(
        evidence,
        key=lambda e: (e.verification_state != "corroborated", -(e.confidence or 0)),
    )
    seen, strongest = set(), []
    for e in ranked:
        key = (e.attribute_type, str(e.value)[:60])
        if key in seen:
            continue
        seen.add(key)
        strongest.append(e)
        if len(strongest) >= 12:
            break

    return {
        "person": person, "evidence": evidence, "sources": sources,
        "coverage": coverage, "dimensions": dimensions,
        "corroborated": len(corroborated), "affiliations": affiliations,
        "works": works, "records": records, "strongest": strongest,
    }


CSS = """
@page { size: A4; margin: 14mm 13mm 16mm; }
* { box-sizing: border-box; }
/* No webfont: a report generator that waits on a font CDN hangs when the
   network is slow and fails outright in a container with no egress. */
body { margin:0; font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
  color:#111113; background:#fff; font-size:10.5pt; line-height:1.5; }
.head { display:flex; align-items:flex-start; gap:14px; border-bottom:2px solid #111113;
  padding-bottom:14px; margin-bottom:22px; }
.mark { width:34px; height:34px; flex:none; }
h1 { font-size:22pt; margin:0; letter-spacing:-.02em; }
.sub { color:#6d6a66; font-size:9.5pt; margin-top:3px; }
.brandmark { margin-left:auto; text-align:right; font-size:8.5pt; color:#6d6a66; }
h2 { font-size:8.5pt; letter-spacing:.16em; text-transform:uppercase; color:#175fff;
  margin:22px 0 8px; font-weight:600; }
h2::before { content:"// "; color:#9c9791; }
table { width:100%; border-collapse:collapse; margin-top:4px; }
th { text-align:left; font-size:7.5pt; letter-spacing:.09em; text-transform:uppercase;
  color:#6d6a66; border-bottom:1px solid #e2ddd6; padding:5px 8px 5px 0; font-weight:600; }
td { padding:6px 8px 6px 0; border-bottom:1px solid #f0ece6; vertical-align:top; font-size:9.5pt; }
td.n, th.n { text-align:right; white-space:nowrap; }
.tag { display:inline-block; background:#efebe6; border-radius:3px; padding:1px 6px;
  font-size:8pt; color:#3a3a3f; margin-right:4px; }
.cov { display:flex; gap:18px; align-items:baseline; margin:6px 0 2px; }
.cov b { font-size:26pt; letter-spacing:-.02em; }
.bar { height:5px; background:#efebe6; border-radius:3px; overflow:hidden; margin-top:8px; }
.bar i { display:block; height:100%; background:#175fff; }
.dims { margin-top:10px; font-size:8.5pt; color:#6d6a66; }
.dims span { margin-right:12px; }
.dims .yes::before { content:"● "; color:#16794c; }
.dims .no::before { content:"○ "; color:#c9c4be; }
a { color:#175fff; text-decoration:none; }
.foot { margin-top:26px; padding-top:10px; border-top:1px solid #e2ddd6;
  font-size:8pt; color:#6d6a66; }
"""


def render_html(data: dict) -> str:
    p = data["person"]
    dims = data["dimensions"]
    rows = "".join(
        f"<tr><td>{_esc(e.value)}</td><td>{_esc(e.attribute_type.replace('_',' '))}</td>"
        f"<td>{_esc(e.source)}</td>"
        f"<td>{'corroborated' if e.verification_state=='corroborated' else ''}</td>"
        f"<td class='n'>{'' if e.url is None else f'<a href=\"{_esc(e.url)}\">link</a>'}</td></tr>"
        for e in data["strongest"]
    )
    affil = "".join(
        f"<tr><td>{_esc(o)}</td><td>{_esc(role or '')}</td><td>{_esc(rel or '')}</td>"
        f"<td class='n'>{_esc(str(sd)[:10] if sd else '')}{' – ' + str(ed)[:10] if ed else ''}</td></tr>"
        for o, role, rel, sd, ed in data["affiliations"][:10]
    )
    works = "".join(
        f"<tr><td>{'<a href=\"' + _esc(u) + '\">' + _esc(t) + '</a>' if u else _esc(t)}</td>"
        f"<td>{_esc(v or '')}</td><td class='n'>{_esc(str(d)[:4] if d else '')}</td>"
        f"<td class='n'>{_esc(c if c is not None else '')}</td></tr>"
        for t, v, d, c, u in data["works"]
    )
    records = "".join(
        f"<tr><td>{_esc(src)}</td>"
        f"<td>{'<a href=\"' + _esc(u) + '\">' + _esc(u)[:78] + '</a>' if u else ''}</td>"
        f"<td class='n'>{_esc(str(seen)[:10] if seen else '')}</td></tr>"
        for src, u, seen in data["records"][:12]
    )
    dim_html = " ".join(
        f"<span class='{'yes' if ok else 'no'}'>{k}</span>" for k, ok in dims.items()
    )
    mark = (f'<svg class="mark" viewBox="0 0 512 512"><path d="{MARK}" fill="#111113" '
            f'fill-rule="evenodd"/></svg>') if MARK else ""
    subtitle = " · ".join(x for x in (p.current_role, p.current_organization,
                                      p.location or p.country) if x)
    return f"""<!doctype html><meta charset="utf-8"><title>{_esc(p.canonical_name)} — Seekr</title>
<style>{CSS}</style>
<div class="head">{mark}
  <div><h1>{_esc(p.canonical_name)}</h1><div class="sub">{_esc(subtitle)}</div></div>
  <div class="brandmark">Seekr · Deccan AI<br>{datetime.now(timezone.utc):%d %B %Y}</div>
</div>

<h2>Evidence coverage</h2>
<div class="cov"><b>{data['coverage']}%</b>
  <div>{len(data['evidence'])} claims from {len(data['sources'])} source{'' if len(data['sources'])==1 else 's'}
    · {data['corroborated']} corroborated by more than one</div></div>
<div class="bar"><i style="width:{data['coverage']}%"></i></div>
<div class="dims">{dim_html}</div>

<h2>Strongest evidence</h2>
<table><tr><th>Claim</th><th>Type</th><th>Source</th><th>Standing</th><th class="n"></th></tr>{rows}</table>

{'<h2>Affiliations</h2><table><tr><th>Organisation</th><th>Role</th><th>Relation</th><th class="n">Dates</th></tr>' + affil + '</table>' if affil else ''}

{'<h2>Selected publications</h2><table><tr><th>Title</th><th>Venue</th><th class="n">Year</th><th class="n">Citations</th></tr>' + works + '</table>' if works else ''}

<h2>Provenance</h2>
<table><tr><th>Source</th><th>Record</th><th class="n">Last seen</th></tr>{records}</table>

<div class="foot">
  Every line above is an attribute a named source stated, with the record it came from.
  Seekr does not infer character, temperament or personal circumstances, and protected
  attributes are redacted at collection. Judgement is the reader's.
</div>
"""
