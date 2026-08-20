import type { ReactElement } from "react";

/* Profile links, drawn as the brand people recognise. Only URLs a source
   actually published — never a handle guessed from someone's name. Ordered by
   how much the link tells you about a person: OpenAlex is on all 50k records
   and identifies nobody, so it sits last. */

export interface Brand {
  host: string;
  label: string;
  color: string;
  paths: string[];
}

export const BRANDS: Brand[] = [
  { host: "linkedin.com", label: "LinkedIn", color: "#0a66c2", paths: ["M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5M2.5 9.5h5V21h-5zM10 9.5h4.7v1.6c.7-1.2 2-1.9 3.6-1.9 3 0 4.2 1.9 4.2 5.2V21h-5v-5.6c0-1.5-.5-2.4-1.8-2.4-1 0-1.6.7-1.9 1.4-.1.2-.1.6-.1.9V21h-5z"] },
  { host: "github.com", label: "GitHub", color: "#24292f", paths: ["M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.3-3.4-1.3-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.6.3-1.1.6-1.3-2.2-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .4.3.7.9.7 1.9v2.8c0 .3.2.6.7.5A10 10 0 0 0 12 2"] },
  { host: "scholar.google.com", label: "Google Scholar", color: "#4285f4", paths: ["M12 2 1 8.5l11 6.5 9-5.3v6.8h2V8.5z", "M5.5 13.2v3.6c0 2 2.9 3.7 6.5 3.7s6.5-1.7 6.5-3.7v-3.6L12 17z"] },
  { host: "orcid.org", label: "ORCID", color: "#a6ce39", paths: ["M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M8.2 6.1a1.1 1.1 0 1 1 0 2.2 1.1 1.1 0 0 1 0-2.2m-.9 3.3h1.8v8.3H7.3zm4 0h3.3c2.6 0 4.2 1.9 4.2 4.2s-1.7 4.1-4.2 4.1h-3.3zm1.8 1.6v5.1h1.4c1.7 0 2.5-1.1 2.5-2.5s-.8-2.6-2.5-2.6z"] },
  { host: "twitter.com", label: "X", color: "#111827", paths: ["M17.5 3h3l-6.6 7.6L21.8 21h-6l-4.7-6.2L5.6 21h-3l7.1-8.1L2.5 3h6.2l4.3 5.7zm-1 16h1.7L7.6 4.7H5.8z"] },
  { host: "x.com", label: "X", color: "#111827", paths: ["M17.5 3h3l-6.6 7.6L21.8 21h-6l-4.7-6.2L5.6 21h-3l7.1-8.1L2.5 3h6.2l4.3 5.7zm-1 16h1.7L7.6 4.7H5.8z"] },
  { host: "stackoverflow.com", label: "Stack Overflow", color: "#f48024", paths: ["M17 21v-6h2v8H3v-8h2v6z", "m6.9 14.7 8.6 1.8.4-2-8.6-1.8zm1.1-4.6 8 3.7.8-1.8-8-3.7zm2.2-4.3 6.8 5.6 1.3-1.5-6.8-5.7zM14.5 1l-1.6 1.2 5.3 7.1 1.6-1.2z"] },
  { host: "huggingface.co", label: "Hugging Face", color: "#ff9d00", paths: ["M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M8.5 9.5a1.2 1.2 0 1 1 0 2.4 1.2 1.2 0 0 1 0-2.4m7 0a1.2 1.2 0 1 1 0 2.4 1.2 1.2 0 0 1 0-2.4M12 18c-2.4 0-4.4-1.6-4.9-3.7h9.8C16.4 16.4 14.4 18 12 18"] },
  { host: "semanticscholar.org", label: "Semantic Scholar", color: "#1857b6", paths: ["M3 4h8.5c5 0 9.5 3.4 9.5 8.5S16.9 21 12 21H3l4-4h5c2.8 0 5-1.9 5-4.5S14.8 8 12 8H3z"] },
  { host: "dblp.org", label: "dblp", color: "#004a99", paths: ["M7 2h6.5c3.6 0 6 2.6 6 6.4V22H13V8.6C13 7 12 6 10.4 6H7zM4.5 10H9v12H4.5z"] },
  { host: "wikipedia.org", label: "Wikipedia", color: "#3366cc", paths: ["M2 5h5.6v1.4l-1.4.3 3.5 8.6 2.3-5.6-1.2-3-1.2-.3V5h5.2v1.4l-1.3.3 3.4 8.6 3.2-8.6-1.5-.3V5H22v1.4l-1.4.4L16.2 20h-1.5l-3-7.2L8.6 20H7.1L2.9 6.8 2 6.4z"] },
  { host: "wikidata.org", label: "Wikidata", color: "#339966", paths: ["M2 6h1.6v12H2zm2.9 0h1.6v12H4.9zm2.9 0h3.2v12H7.8zm4.5 0H14v12h-1.7zm3 0h3.2v12h-3.2zM22 6h-1.6v12H22z"] },
  { host: "researchgate.net", label: "ResearchGate", color: "#00ccbb", paths: ["M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m-2.6 6h2.4c1.6 0 2.6 1 2.6 2.4 0 1.1-.6 1.9-1.6 2.2l2 3.4h-1.8l-1.8-3.1h-.6V16H9.4zm1.2 1.3v2.4h1c.8 0 1.3-.4 1.3-1.2s-.5-1.2-1.3-1.2z"] },
  { host: "openalex.org", label: "OpenAlex", color: "#7c3aed", paths: ["M12 2 2 20h4l6-11 6 11h4z"] },
];

export const MAX_BRAND_LINKS = 6;

function hostMatches(url: string, host: string): boolean {
  try {
    const h = new URL(url).hostname.replace(/^www\./, "");
    return h === host || h.endsWith("." + host);
  } catch {
    return false;
  }
}

/** One link per brand, in BRANDS order, capped so a well-covered person does
 *  not turn the name column into a link farm. */
export function BrandLinks({
  urls,
  max = MAX_BRAND_LINKS,
}: {
  urls?: string[] | null;
  max?: number;
}): ReactElement | null {
  const seen = new Set<string>();
  const found: { brand: Brand; url: string }[] = [];
  for (const brand of BRANDS) {
    if (found.length >= max) break;
    if (seen.has(brand.label)) continue;
    const hit = (urls || []).find((u) => hostMatches(u, brand.host));
    if (!hit) continue;
    seen.add(brand.label);
    found.push({ brand, url: hit });
  }
  if (!found.length) return null;
  return (
    <div className="plinks">
      {found.map(({ brand, url }) => (
        <a
          key={brand.label}
          className="plink"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          title={brand.label}
          aria-label={brand.label}
          style={{ ["--plink" as string]: brand.color } as React.CSSProperties}
          onClick={(e) => e.stopPropagation()}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="10" height="10">
            {brand.paths.map((d, i) => (
              <path key={i} d={d} />
            ))}
          </svg>
        </a>
      ))}
    </div>
  );
}
