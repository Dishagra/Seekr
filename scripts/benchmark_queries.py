"""Run a suite of realistic queries and report how Seekr handles each.

Local-only by default (no paid calls). Reports, per query: how many people
matched, which filters were applied, and which terms were dropped — so a bad
result can be traced to parsing, coverage, or both.
"""

import json
import os
import sys
import urllib.parse
import urllib.request

BASE = os.environ.get("SEEKR_BASE", "http://127.0.0.1:8000")
TOKEN = os.environ.get("SEEKR_TOKEN", "localdev")

QUERIES = [
    # --- easy
    "Product designers at Deccan.ai", "ML engineers at OpenAI",
    "Backend engineers in Bangalore", "Researchers at IIT Bombay working on robotics",
    "Data scientists at Google India", "Founders of Indian AI startups",
    "Python developers in Mumbai", "UX designers with fintech experience",
    "Computer vision researchers", "Rust developers in India",
    "Engineers who have worked at both Google and Microsoft",
    "Open source maintainers in India", "Product managers at SaaS companies",
    "AI researchers from Stanford", "Cybersecurity engineers in Bangalore",
    # --- medium
    "Distributed systems engineers who have worked at large-scale tech companies",
    "Indian researchers publishing papers on reinforcement learning",
    "Product designers who have worked on developer tools",
    "Engineers contributing to popular Kubernetes projects",
    "Researchers in India working on multimodal AI",
    "Machine learning engineers with experience deploying models in production",
    "Backend engineers who specialize in high-throughput systems",
    "Computer science PhDs working on LLM evaluation",
    "Engineers who have contributed to major open-source databases",
    "Product designers with experience in AI products and enterprise SaaS",
    "Robotics engineers who have published papers and worked in industry",
    "People working on privacy-preserving machine learning in Europe",
    "Software engineers who have spoken at engineering conferences about distributed systems",
    "Data engineers with experience at fintech companies and strong open-source contributions",
    "Researchers who work on compiler optimization and have industry experience",
    # --- complex
    "Find researchers in India working on multimodal AI who have published at NeurIPS, ICML, or ACL and currently work outside academia",
    "Find engineers who have contributed significantly to Kubernetes and have worked at companies operating large-scale distributed systems",
    "Product designers who have designed AI-native products, have experience at an early-stage startup, and currently work in India",
    "Find people who have both academic research and production engineering experience in reinforcement learning",
    "Software engineers in India who specialize in distributed databases, have public GitHub contributions, and have previously worked at Google, Amazon, Microsoft, or Meta",
    "Find researchers working on LLM reasoning or evaluation with publications from the last three years and a public research profile",
    "Find robotics researchers who have both peer-reviewed publications and substantial open-source projects",
    "Indian computer scientists with expertise in compilers who have published research and worked in industry",
    "Find cybersecurity researchers who have published on vulnerability discovery and contribute to open source",
    "Find ML engineers who have worked on model training infrastructure and contributed to open-source ML tooling",
    "Researchers who have moved from academia into AI startups and continue to publish publicly",
    "Engineers with expertise in high-performance computing who have contributed to open-source systems projects",
    # --- messy / conversational
    "I need someone really good at distributed systems, ideally someone who's built this stuff at scale and has some public work to show",
    "Find me a few people who actually understand AI infrastructure, not just ML modeling",
    "Looking for a researcher who knows reinforcement learning really well but has also spent time building real products",
    "Who are the strongest open-source contributors in India working on databases?",
    "Find people who seem unusually strong in computer vision",
    # --- stress tests
    "People who worked at DeepMind and later joined an AI startup",
    "Researchers who published on graph neural networks and have open-source implementations on GitHub",
    "Engineers who contributed to PostgreSQL and have experience building distributed systems",
    "Indian AI researchers with publications at top conferences and a public GitHub presence",
    "People with experience in both robotics and computer vision who have published research since 2023",
    "Strong generalist engineers who have worked across backend, infrastructure, and ML systems",
    "Experts in low-level systems programming",
]


def run(query: str, discover: str = "false") -> dict:
    url = f"{BASE}/v1/query?q={urllib.parse.quote(query)}&discover={discover}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def main() -> None:
    discover = sys.argv[1] if len(sys.argv) > 1 else "false"
    rows, zero, thin, good = [], [], [], []
    for q in QUERIES:
        try:
            d = run(q, discover)
        except Exception as exc:
            rows.append((q, -1, f"ERROR {exc}"))
            continue
        f = d["applied_filters"]
        applied = []
        for key, label in (("skills", "skill"), ("skill_patterns", "skill~"),
                           ("organizations", "org"), ("locations", "loc"),
                           ("countries", "country"), ("name_terms", "name")):
            for v in f.get(key) or []:
                applied.append(f"{label}:{v}")
        n = max(d["total_matches"], d.get("count") or 0)
        rows.append((q, n, applied, d["unmatched_terms"], d.get("empty_reason")))
        (good if n >= 3 else thin if n else zero).append(q)

    print(f"{'n':>6}  query / filters / dropped")
    print("-" * 100)
    for r in rows:
        q, n = r[0], r[1]
        print(f"{n:>6}  {q[:76]}")
        if len(r) > 3:
            if r[2]:
                print(f"{'':>8}applied: {', '.join(str(x)[:40] for x in r[2])[:110]}")
            if r[3]:
                print(f"{'':>8}dropped: {', '.join(r[3])[:110]}")
            if len(r) > 4 and r[4]:
                print(f"{'':>8}why-empty: {r[4]['message'][:100]}")
    total = len(QUERIES)
    print("-" * 100)
    print(f"3+ results: {len(good)}/{total}   1-2: {len(thin)}/{total}   zero: {len(zero)}/{total}")


if __name__ == "__main__":
    main()
