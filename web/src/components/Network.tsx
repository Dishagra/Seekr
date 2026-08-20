import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { GraphEdge, GraphNode } from "../types";

/** Radial layout with label-box separation; no external library.
 *
 *  Labels, not dots, are what collide in a co-author graph, so the relaxation
 *  pass below pushes nodes apart by the width of their rendered text rather
 *  than by a fixed radius.
 */

const MAX_LABEL = 20;
const PASSES = 160;

interface Placed extends GraphNode {
  x: number;
  y: number;
  fixed?: boolean;
}

const shorten = (s: string): string =>
  (s || "").length > MAX_LABEL ? s.slice(0, MAX_LABEL - 1) + "…" : s || "";

const halfWidth = (s: string): number => Math.max(24, shorten(s).length * 3.1 + 8);

function layout(nodes: GraphNode[], selfId: string, W: number, H: number): Placed[] {
  const cx = W / 2;
  const cy = H / 2;
  const others = nodes.filter((n) => n.id !== selfId);
  const rings = Math.max(1, Math.ceil(others.length / 9));

  const placed: Placed[] = nodes.map((n) => {
    if (n.id === selfId) return { ...n, x: cx, y: cy, fixed: true };
    const k = others.indexOf(n);
    const ring = k % rings;
    const a = (k / Math.max(1, others.length)) * Math.PI * 2 - Math.PI / 2;
    const base = n.type === "organization" ? 92 : 148 + ring * 112;
    return {
      ...n,
      x: cx + Math.cos(a) * base * (W / H) * 0.78,
      y: cy + Math.sin(a) * base * 0.72,
    };
  });

  for (let pass = 0; pass < PASSES; pass++) {
    for (const a of placed) {
      if (a.fixed) continue;
      for (const b of placed) {
        if (a === b) continue;
        const needX = halfWidth(a.label) + halfWidth(b.label) + 10;
        const needY = 30;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        if (Math.abs(dx) < needX && Math.abs(dy) < needY) {
          if (Math.abs(dx) / needX > Math.abs(dy) / needY) {
            a.x += (needX - Math.abs(dx)) * 0.22 * (dx < 0 ? -1 : 1);
          } else {
            a.y += (needY - Math.abs(dy)) * 0.5 * (dy < 0 ? -1 : 1);
          }
        }
      }
      a.x = Math.max(halfWidth(a.label) + 6, Math.min(W - halfWidth(a.label) - 6, a.x));
      a.y = Math.max(24, Math.min(H - 14, a.y));
    }
  }
  return placed;
}

export function Network({
  nodes,
  edges,
  selfId,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selfId: string;
}) {
  const navigate = useNavigate();
  const W = 900;
  const H = Math.min(700, 280 + Math.max(1, Math.ceil((nodes.length - 1) / 9)) * 115);
  const cy = H / 2;

  const placed = useMemo(() => layout(nodes, selfId, W, H), [nodes, selfId, H]);
  const byId = useMemo(
    () => Object.fromEntries(placed.map((n) => [n.id, n])),
    [placed],
  );

  return (
    <div className="net">
      <svg viewBox={`0 0 ${W} ${H}`}>
        {edges.map((e, i) => {
          const a = byId[e.from];
          const b = byId[e.to];
          if (!a || !b) return null;
          const title =
            e.type === "coauthor"
              ? `${e.shared_publications} shared publication(s)`
              : e.type;
          return (
            <line
              key={i}
              className={e.type === "coauthor" ? "edge" : "edge org"}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
            >
              <title>{title}</title>
            </line>
          );
        })}
        {placed.map((n) => {
          const dy = n.y < cy ? -11 : 17;
          if (n.type === "organization") {
            return (
              <g key={n.id}>
                <rect
                  className="n-org"
                  x={n.x - 5}
                  y={n.y - 5}
                  width={10}
                  height={10}
                  rx={2}
                >
                  <title>{n.label}</title>
                </rect>
                <text x={n.x} y={n.y + dy} textAnchor="middle">
                  {shorten(n.label)}
                </text>
              </g>
            );
          }
          const isSelf = n.id === selfId;
          return (
            <g
              key={n.id}
              onClick={isSelf ? undefined : () => navigate(`/person/${n.id}`)}
              style={isSelf ? undefined : { cursor: "pointer" }}
            >
              <circle
                className={isSelf ? "n-person n-self" : "n-person"}
                cx={n.x}
                cy={n.y}
                r={isSelf ? 8 : 5.5}
              >
                <title>{n.label}</title>
              </circle>
              <text x={n.x} y={n.y + dy} textAnchor="middle">
                {shorten(n.label)}
              </text>
            </g>
          );
        })}
      </svg>
      <span className="legend">■ organization · ● co-author</span>
    </div>
  );
}
