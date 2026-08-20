import { useEffect, useState } from "react";
import { api, errorMessage, isUnauthorized } from "../api/client";
import { Banner, Loading } from "../components/EmptyState";
import { Shell } from "../components/Shell";
import { fmt, minute } from "../lib/format";
import { useWorking } from "../lib/hooks";
import type { FacetResponse, SourceHealth, WebhookHealth } from "../types";

interface Runs {
  ok: number;
  error: number;
  last: string | null;
}

interface Page {
  coverage: FacetResponse;
  runs: Record<string, Runs>;
  hooks: WebhookHealth | null;
}

/** Health rows arrive one per run status, so they are folded into a single
 *  ok/failed pair per source before anything is drawn. */
function foldRuns(rows: SourceHealth[]): Record<string, Runs> {
  const runs: Record<string, Runs> = {};
  for (const s of rows) {
    const entry = (runs[s.source] ||= { ok: 0, error: 0, last: null });
    entry[s.status === "ok" ? "ok" : "error"] += s.runs;
    if (s.last_finished_at) entry.last = s.last_finished_at;
  }
  return runs;
}

export function Sources() {
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);

  useWorking(!page && !error);

  useEffect(() => {
    let live = true;
    Promise.all([
      api<FacetResponse>("/v1/facets?field=source"),
      api<{ sources: SourceHealth[] }>("/v1/health/sources"),
      api<WebhookHealth>("/v1/webhooks/health").catch(() => null),
    ])
      .then(([coverage, health, hooks]) => {
        if (!live) return;
        setPage({ coverage, runs: foldRuns(health.sources || []), hooks });
      })
      .catch((e) => {
        if (live && !isUnauthorized(e)) setError(errorMessage(e));
      });
    return () => {
      live = false;
    };
  }, []);

  const topbar = (
    <>
      <h1 className="title">Sources</h1>
      <div className="sub">Where the data comes from, and whether ingestion is healthy.</div>
    </>
  );

  if (error) {
    return (
      <Shell topbar={topbar}>
        <Banner>{error}</Banner>
      </Shell>
    );
  }
  if (!page) {
    return (
      <Shell topbar={topbar}>
        <Loading message="Loading…" />
      </Shell>
    );
  }

  const { hooks } = page;

  return (
    <Shell topbar={topbar}>
      <section className="block">
        <h2>Coverage</h2>
        <div className="card">
          <div className="tablewrap">
            <table className="list">
              <thead>
                <tr>
                  <th>Source</th>
                  <th className="num">People</th>
                  <th className="num">Runs OK</th>
                  <th className="num">Failed</th>
                  <th>Last run</th>
                </tr>
              </thead>
              <tbody>
                {page.coverage.values.map((v) => {
                  const r = page.runs[v.value] || { ok: 0, error: 0, last: null };
                  return (
                    <tr key={v.value}>
                      <td className="nm">{v.value}</td>
                      <td className="num">{fmt(v.people)}</td>
                      <td className="num">{fmt(r.ok)}</td>
                      <td className="num">
                        {r.error ? (
                          <span style={{ color: "var(--danger)" }}>{fmt(r.error)}</span>
                        ) : (
                          "0"
                        )}
                      </td>
                      <td className="muted">{minute(r.last) || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {hooks && (
        <section className="block">
          <h2>Webhook delivery</h2>
          <div className="card">
            <div className="inner">
              <table className="data">
                <tbody>
                  <tr>
                    <td>Active subscriptions</td>
                    <td className="num">{fmt(hooks.active_subscriptions)}</td>
                  </tr>
                  <tr>
                    <td>Pending</td>
                    <td className="num">
                      {hooks.pending ? (
                        <span style={{ color: "var(--warn)" }}>{fmt(hooks.pending)}</span>
                      ) : (
                        "0"
                      )}
                    </td>
                  </tr>
                  <tr>
                    <td>Delivered</td>
                    <td className="num">{fmt(hooks.delivered)}</td>
                  </tr>
                  <tr>
                    <td>Failed</td>
                    <td className="num">
                      {hooks.failed ? (
                        <span style={{ color: "var(--danger)" }}>{fmt(hooks.failed)}</span>
                      ) : (
                        "0"
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
              {hooks.pending > 0 && (
                <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
                  Deliveries only send when <code>deliver-webhooks</code> runs.
                </p>
              )}
            </div>
          </div>
        </section>
      )}
    </Shell>
  );
}
