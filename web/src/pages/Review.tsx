import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiSend, errorMessage, isUnauthorized } from "../api/client";
import { Banner, EmptyState, Loading } from "../components/EmptyState";
import { Shell } from "../components/Shell";
import { useWorking } from "../lib/hooks";
import type { DuplicateCandidate, FuzzyMerge } from "../types";

interface Queue {
  possible_duplicates: DuplicateCandidate[];
  fuzzy_merges: FuzzyMerge[];
}

export function Review() {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  useWorking(!queue && !error);

  const load = useCallback(() => {
    api<Queue>("/v1/review/merges")
      .then(setQueue)
      .catch((e) => {
        if (!isUnauthorized(e)) setError(errorMessage(e));
      });
  }, []);

  useEffect(load, [load]);

  /** Every decision here rewrites identity, so the queue is re-read rather
   *  than patched in place — a merge can change more rows than the one acted
   *  on. */
  const act = async (path: string) => {
    setActing(true);
    setError(null);
    try {
      await apiSend(path, "POST");
      setQueue(null);
      load();
    } catch (e) {
      if (!isUnauthorized(e)) setError(errorMessage(e));
    } finally {
      setActing(false);
    }
  };

  const topbar = (
    <>
      <h1 className="title">Review queue</h1>
      <div className="sub">
        Merges Seekr was not confident enough to make on its own. Every decision is
        reversible.
      </div>
    </>
  );

  if (error) {
    return (
      <Shell topbar={topbar}>
        <Banner>{error}</Banner>
      </Shell>
    );
  }
  if (!queue) {
    return (
      <Shell topbar={topbar}>
        <Loading message="Loading queue…" />
      </Shell>
    );
  }

  const duplicates = queue.possible_duplicates || [];
  const fuzzy = queue.fuzzy_merges || [];

  return (
    <Shell topbar={topbar}>
      <section className="block">
        <h2>
          Possible duplicates <span className="n">{duplicates.length}</span>
        </h2>
        {duplicates.length ? (
          duplicates.map((d) => (
            <div className="conflict" key={d.candidate_id}>
              <div className="vs">
                <div className="side">
                  <b>
                    <Link to={`/person/${d.person_id}`}>{d.person_name}</Link>
                  </b>
                </div>
                <div className="mid">same person?</div>
                <div className="side">
                  <b>
                    <Link to={`/person/${d.duplicate_person_id}`}>
                      {d.duplicate_person_name}
                    </Link>
                  </b>
                </div>
              </div>
              <div className="idline">{d.signals?.reason || `score ${d.score}`}</div>
              <div className="btn-row" style={{ marginTop: 10 }}>
                <button
                  className="btn primary sm"
                  disabled={acting}
                  onClick={() => act(`/v1/review/duplicates/${d.candidate_id}/merge`)}
                >
                  Merge
                </button>
                <button
                  className="btn danger sm"
                  disabled={acting}
                  onClick={() => act(`/v1/review/duplicates/${d.candidate_id}/reject`)}
                >
                  Different people
                </button>
              </div>
            </div>
          ))
        ) : (
          <EmptyState title="Nothing to review" body="No duplicate pairs are waiting." />
        )}
      </section>

      <section className="block">
        <h2>
          Fuzzy merges awaiting confirmation <span className="n">{fuzzy.length}</span>
        </h2>
        {fuzzy.length ? (
          fuzzy.map((f) => (
            <div className="conflict" key={f.link_id}>
              <div>
                <b>
                  <Link to={`/person/${f.person_id}`}>{f.person_name}</Link>
                </b>{" "}
                <span className="muted">
                  ← {f.source}:{f.external_id} ({f.record_name || ""})
                </span>
              </div>
              <div className="idline">{f.signals?.reason || f.match_method}</div>
              <div className="btn-row" style={{ marginTop: 10 }}>
                <button
                  className="btn primary sm"
                  disabled={acting}
                  onClick={() => act(`/v1/review/merges/${f.link_id}/approve`)}
                >
                  Approve
                </button>
                <button
                  className="btn danger sm"
                  disabled={acting}
                  onClick={() => act(`/v1/review/merges/${f.link_id}/split`)}
                >
                  Split apart
                </button>
              </div>
            </div>
          ))
        ) : (
          <EmptyState
            title="All confirmed"
            body="No fuzzy merges are waiting for a decision."
          />
        )}
      </section>
    </Shell>
  );
}
