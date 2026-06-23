"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8787";
const REFRESH_MS = 15000;

// One normalized event row from the local store (api/missioncontrol/models.py::Event).
// `payload` is scrubbed before persistence, so any auth-bearing value is "<redacted>".
type MCEvent = {
  id: number | null;
  surface: string;
  source: string;
  session_id: string | null;
  work_thread_id: string | null;
  type: string;
  ts: number;
  severity: string;
  payload: Record<string, unknown>;
};
type TimelineResp = { events: MCEvent[]; degraded?: string };

// Identical events (e.g. a 30s quota heartbeat) collapse into one row with a count, so the feed
// reads as "what happened", not a wall of duplicates. Nothing is hidden: the count and the time
// span (first-seen on hover) are shown, and any genuine change is a distinct row.
type Group = {
  key: string;
  head: MCEvent; // a representative (the newest occurrence; events arrive newest-first)
  count: number;
  newestTs: number;
  oldestTs: number;
};

// --- tolerant payload readers (the store is the boundary; never trust shape) -----------------
function asNum(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function asStr(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

const fmtNum = (n: number): string => n.toLocaleString("en-US");
const fmtUsd = (n: number): string =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

function summarizeCodex(p: Record<string, unknown>): string {
  const windows = Array.isArray(p.windows) ? p.windows : [];
  const parts: string[] = [];
  for (const w of windows) {
    if (typeof w !== "object" || w === null) continue;
    const ww = w as Record<string, unknown>;
    const rem = asNum(ww.remaining_pct);
    const label = asStr(ww.window) ?? "window";
    if (rem !== null) parts.push(`${label} ${Math.round(rem)}%`);
  }
  return parts.length > 0 ? `${parts.join(" · ")} left` : "quota snapshot";
}

function summarizeClaude(p: Record<string, unknown>): string {
  // token counts persist as "<redacted>" (key matches the auth-key scrubber), so report what
  // survives truthfully: message count + the cost estimate.
  const bits: string[] = [];
  const evs = asNum(p.events);
  const cost = asNum(p.estimated_cost_usd);
  if (evs !== null) bits.push(`${fmtNum(evs)} messages`);
  if (cost !== null) bits.push(`~${fmtUsd(cost)} est.`);
  return bits.length > 0 ? bits.join(" · ") : "usage snapshot";
}

function summarize(e: MCEvent): string {
  const p = e.payload ?? {};
  if (e.type.startsWith("alert.")) return asStr(p.message) ?? kindLabel(e.type);
  if (e.type === "quota.snapshot") {
    if (e.surface === "codex") return summarizeCodex(p);
    if (e.surface === "claude") return summarizeClaude(p);
    return "quota snapshot";
  }
  if (e.type === "collector.status") {
    const d = asStr(p.degraded);
    return d ? `degraded — ${d}` : "collector status";
  }
  return kindLabel(e.type);
}

const KIND_LABELS: Record<string, string> = {
  "quota.snapshot": "snapshot",
  "collector.status": "status",
  "alert.throttle": "throttle",
  "alert.headroom": "headroom",
};
function kindLabel(type: string): string {
  return KIND_LABELS[type] ?? type.split(".").pop() ?? type;
}

function sevClass(severity: string): string {
  if (severity === "crit") return "crit";
  if (severity === "warn") return "warn";
  return "info";
}

function ago(ts: number, now: number): string {
  const d = now - ts;
  if (d < 5) return "just now";
  if (d < 60) return `${d}s ago`;
  const m = Math.floor(d / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function absTime(ts: number): string {
  const d = new Date(ts * 1000);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
}

// Collapse identical events (same surface/type/severity/summary) into one row with a count.
// Heartbeat snapshots interleave by surface, so adjacency collapse wouldn't fire; key-collapse
// compresses idle repeats while every genuine *change* (e.g. rising cost) stays its own row.
// Input is newest-first, so a key's first sighting is its newest occurrence — order is preserved.
function collapse(events: MCEvent[]): Group[] {
  const byKey = new Map<string, Group>();
  const order: Group[] = [];
  for (const e of events) {
    const key = `${e.surface}|${e.type}|${e.severity}|${summarize(e)}`;
    const g = byKey.get(key);
    if (g) {
      g.count += 1;
      g.oldestTs = Math.min(g.oldestTs, e.ts);
      g.newestTs = Math.max(g.newestTs, e.ts);
    } else {
      const ng: Group = {
        key,
        head: e,
        count: 1,
        newestTs: e.ts,
        oldestTs: e.ts,
      };
      byKey.set(key, ng);
      order.push(ng);
    }
  }
  return order;
}

function EventRow({ g, now }: { g: Group; now: number }) {
  const e = g.head;
  return (
    <div className="evt">
      <span className={`sev ${sevClass(e.severity)}`} aria-hidden="true" />
      <div className="evt-body">
        <div className="evt-head">
          <span className="surface">{e.surface}</span>
          <span className="kind">{kindLabel(e.type)}</span>
          {g.count > 1 && (
            <span className="count" title={`first seen ${absTime(g.oldestTs)}`}>
              ×{g.count}
            </span>
          )}
          <span className="spacer" />
          <span className="evt-ts" title={absTime(g.newestTs)}>
            {ago(g.newestTs, now)}
          </span>
        </div>
        <div className="evt-summary">{summarize(e)}</div>
      </div>
    </div>
  );
}

export default function Timeline() {
  const [data, setData] = useState<TimelineResp | null>(null);
  const [down, setDown] = useState(false);
  const [filter, setFilter] = useState<string>("all");
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetch(`${API}/api/timeline?limit=500`)
        .then((r) => r.json())
        .then((d: TimelineResp) => {
          if (alive) {
            setData(d);
            setDown(false);
            setNow(Math.floor(Date.now() / 1000));
          }
        })
        .catch(() => {
          if (alive) setDown(true);
        });
    };
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const events = data?.events ?? [];
  const surfaces = Array.from(new Set(events.map((e) => e.surface))).sort();
  const shown =
    filter === "all" ? events : events.filter((e) => e.surface === filter);
  const groups = collapse(shown);

  return (
    <main className="app">
      <header className="brand">
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          style={{ color: "var(--brand)" }}
          aria-hidden="true"
        >
          <circle
            cx="12"
            cy="12"
            r="10.5"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <circle
            cx="12"
            cy="12"
            r="6.2"
            stroke="currentColor"
            strokeWidth="1.1"
            opacity="0.5"
          />
          <line
            x1="12"
            y1="12"
            x2="19.8"
            y2="5.6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <circle cx="17" cy="8.4" r="1.7" fill="currentColor" />
          <circle cx="12" cy="12" r="1.05" fill="currentColor" />
        </svg>
        <span className="wordmark">Mission Control</span>
        <span className="tag">timeline</span>
        <span className="spacer" />
        <nav className="nav">
          <Link href="/">Dashboard</Link>
          <Link href="/watch">Watch</Link>
          <Link href="/timeline" className="active">
            Timeline
          </Link>
        </nav>
      </header>

      <div className="toggle">
        <button
          className={filter === "all" ? "on" : ""}
          onClick={() => setFilter("all")}
          type="button"
        >
          All
        </button>
        {surfaces.map((s) => (
          <button
            key={s}
            className={filter === s ? "on" : ""}
            onClick={() => setFilter(s)}
            type="button"
          >
            {s}
          </button>
        ))}
      </div>

      {down && (
        <div className="notice">
          Cannot reach the API at <code>{API}</code>. Start it with{" "}
          <code>
            uv --directory api run uvicorn missioncontrol.main:app --host
            127.0.0.1 --port 8787
          </code>
          .
        </div>
      )}

      {!down && data?.degraded && (
        <div className="notice">Timeline degraded — {data.degraded}.</div>
      )}

      {!down && data && groups.length === 0 && (
        <div className="card">
          <div className="sub">
            No activity recorded yet. Open the{" "}
            <Link href="/" className="inline-link">
              Dashboard
            </Link>{" "}
            to start the live feed — events accrue while it is open.
          </div>
        </div>
      )}

      {!down && groups.length > 0 && (
        <div className="timeline">
          {groups.map((g) => (
            <EventRow key={g.key} g={g} now={now} />
          ))}
        </div>
      )}
    </main>
  );
}
