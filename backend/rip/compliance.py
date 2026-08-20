"""Protected-attribute screening for free text we collect about people.

Seekr feeds hiring decisions, so material about someone's family, faith,
health, age, citizenship or gender identity must not become a queryable
attribute of them — however incidentally a source mentions it. Raw payloads
keep the original text for provenance; this decides what is allowed to
surface as evidence.

The idea is borrowed from the recruitment screener, which scanned finished
reports for protected terms. Two changes. It runs at ingest instead, because
the compliant place to stop collecting something is where it is collected.
And it demands that the term actually refer to the person: the screener's
patterns flagged a bare "children", which in this corpus matched a
researcher whose stated interest is "how technology is affecting children
and society" — a topic, not a family.
"""

from __future__ import annotations

import re

# Anchors that make a mention personal rather than topical.
_MINE = r"(?:i'?m|i am|my|me|he|she|they|his|her|their|our)"

PROTECTED_PATTERNS: dict[str, str] = {
    # "father of two", "my wife", "happily married" — not "children's health"
    "family_status": (
        rf"\b(?:{_MINE}\s+(?:wife|husband|spouse|partner|children|kids|son|daughter)"
        r"|(?:proud\s+)?(?:father|mother|dad|mum|mom)\s+of\s+\w+"
        r"|happily\s+married|newly\s?wed"
        rf"|{_MINE}\s+(?:pregnancy|maternity|paternity))\b"
    ),
    # a stated age or birth year, not the word "born" in "born in Berlin"
    "age": (
        r"\b(?:aged?\s+\d{1,2}\b|\d{1,2}\s+years?\s+old"
        r"|born\s+in\s+(?:19|20)\d{2}|d\.?o\.?b\.?\s*[:.]"
        r"|date\s+of\s+birth)\b"
    ),
    # self-identification, not the study of religion — and never a bare
    # "Christian", which is a given name carried by people in this graph
    "religion": (
        rf"\b(?:{_MINE}\s+(?:faith|religion)"
        r"|(?:practot|practis|practic)\w*\s+(?:hindu|muslim|christian|jew|sikh|buddhist|catholic)"
        r"|(?:devout|observant)\s+\w+"
        rf"|{_MINE}\s+(?:church|mosque|temple|synagogue))\b"
    ),
    "health_disability": (
        rf"\b(?:{_MINE}\s+(?:disability|diagnosis|illness|condition|medication)"
        r"|chronically\s+ill|registered\s+disabled"
        rf"|{_MINE}\s+(?:mental\s+health|depression|anxiety)"
        r"|neurodivergent|autistic|adhd)\b"
    ),
    # immigration status, which is not the same as work authorisation
    "citizenship": (
        r"\b(?:citizen\s+of\s+\w+|dual\s+citizenship|green\s?card"
        r"|permanent\s+resident|asylum\s+seeker|refugee\s+status)\b"
    ),
    # a pronoun declaration is gender data, and is common in profile bios
    "gender_identity": (
        r"\b(?:pronouns?\s*[:\-]\s*\w+/\w+|\b(?:he|she|they)/(?:him|her|them)\b"
        r"|transgender|non-?binary|genderqueer)\b"
    ),
    "sexual_orientation": r"\b(?:gay|lesbian|bisexual|asexual|lgbtq\+?)\b",
}

# Job-relevant phrases that would otherwise trip the patterns above. Work
# authorisation is a lawful hiring question in most jurisdictions; citizenship
# is not, and the two share vocabulary.
ALLOWLIST = (
    "work authorization", "work authorisation", "visa sponsorship",
    "visa transfer", "h-1b sponsorship", "o-1 sponsorship", "right to work",
)

_COMPILED = {k: re.compile(v, re.I) for k, v in PROTECTED_PATTERNS.items()}


def scan(text: str | None) -> list[dict]:
    """Protected-attribute mentions that appear to be about the person."""
    if not text:
        return []
    haystack = text
    for phrase in ALLOWLIST:
        haystack = re.sub(re.escape(phrase), " " * len(phrase), haystack, flags=re.I)
    out: list[dict] = []
    for kind, rx in _COMPILED.items():
        for m in rx.finditer(haystack):
            out.append({"kind": kind, "span": (m.start(), m.end()), "text": m.group(0)})
    return out


def redact(text: str | None) -> tuple[str | None, list[str]]:
    """Replace protected spans, keeping the rest of the text usable.

    Dropping a whole bio because it ends with "pronouns: she/her" would throw
    away the sentence that says what someone builds. The span goes, the
    substance stays, and the kind is named so the removal is visible rather
    than silent.
    """
    findings = scan(text)
    if not findings or text is None:
        return text, []
    out, kinds = text, []
    for f in sorted(findings, key=lambda f: f["span"][0], reverse=True):
        start, end = f["span"]
        out = f"{out[:start]}[redacted: {f['kind']}]{out[end:]}"
        kinds.append(f["kind"])
    return out, sorted(set(kinds))
