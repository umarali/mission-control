"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8787";

type QWindow = {
  window: string;
  window_minutes: number | null;
  remaining_pct: number | null;
  used_pct: number | null;
  resets_at: number | null;
  blocked: boolean;
  stale: boolean;
};
type CodexQuota = {
  available: boolean;
  windows: QWindow[];
  degraded: string | null;
};
type ClaudeConsumed = {
  available: boolean;
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
  total_tokens: number;
  events: number;
  degraded: string | null;
  estimated_cost_usd: number | null;
  pricing_as_of: string | null;
  // Remaining-window quota (credentialed, opt-in) merged alongside the consumed totals.
  windows: QWindow[];
  quota_available: boolean;
  quota_degraded: string | null;
};
type Snapshot = {
  generated_at: number;
  codex: CodexQuota;
  claude: ClaudeConsumed;
};

type Status = "ok" | "warn" | "crit" | "muted";

function statusOf(remaining: number | null, blocked: boolean): Status {
  if (blocked) return "crit";
  if (remaining === null) return "muted";
  if (remaining < 5) return "crit";
  if (remaining < 20) return "warn";
  return "ok";
}

function fmtCountdown(resetsAt: number | null, now: number): string {
  if (resetsAt === null) return "—";
  const d = resetsAt - now;
  if (d <= 0) return "now";
  const days = Math.floor(d / 86400);
  const h = Math.floor((d % 86400) / 3600);
  const m = Math.floor((d % 3600) / 60);
  const s = d % 60;
  if (days > 0) return `${days}d ${h}h`;
  return h > 0
    ? `${h}h ${String(m).padStart(2, "0")}m`
    : `${m}m ${String(s).padStart(2, "0")}s`;
}

const fmtNum = (n: number): string => n.toLocaleString("en-US");

function badgeFor(st: Status, blocked: boolean): { cls: string; text: string } {
  if (blocked) return { cls: "crit", text: "blocked" };
  if (st === "crit") return { cls: "crit", text: "low" };
  if (st === "warn") return { cls: "warn", text: "caution" };
  if (st === "muted") return { cls: "muted", text: "no data" };
  return { cls: "ok", text: "ok" };
}

function GaugeCard({
  w,
  now,
  label,
}: {
  w: QWindow;
  now: number;
  label: string;
}) {
  const st = statusOf(w.remaining_pct, w.blocked);
  const remaining = w.remaining_pct;
  const width = remaining === null ? 0 : Math.max(0, Math.min(100, remaining));
  // Stale = the window reset but the source still shows the pre-reset number. Don't trust it:
  // mute the bar, badge it "stale", and say a refresh is pending instead of a false reading.
  const stale = w.stale;
  const fillClass = stale ? "muted" : st;
  const badge = stale
    ? { cls: "muted", text: "stale" }
    : badgeFor(st, w.blocked);
  const soonFrac =
    w.window_minutes && w.resets_at
      ? (w.resets_at - now) / (w.window_minutes * 60)
      : 1;
  const headroom =
    !stale &&
    st === "ok" &&
    remaining !== null &&
    remaining > 40 &&
    soonFrac > 0 &&
    soonFrac < 0.2;

  return (
    <div className="card">
      <div className="gauge-head">
        <span className="gauge-label">{label}</span>
        <span className="gauge-window">{w.window}</span>
      </div>
      <div className="gauge-value">
        {remaining === null ? "—" : remaining}
        <span className="pct"> % left</span>
      </div>
      <div className="track">
        <div className={`fill ${fillClass}`} style={{ width: `${width}%` }} />
      </div>
      <div className="reset">
        <span className={`badge ${badge.cls}`}>{badge.text}</span>
        <span>
          {stale ? (
            "awaiting reset"
          ) : (
            <>
              resets in{" "}
              <span className="mono">{fmtCountdown(w.resets_at, now)}</span>
            </>
          )}
        </span>
      </div>
      {headroom && (
        <div className="nudge">
          {remaining}% unused and resetting soon — queue work now or it is lost.
        </div>
      )}
      {!stale && st === "crit" && (
        <div className="nudge crit">
          Throttle risk — almost out for this window.
        </div>
      )}
    </div>
  );
}

function Gauges({
  label,
  available,
  windows,
  degraded,
  now,
  loading,
}: {
  label: string;
  available: boolean;
  windows: QWindow[];
  degraded: string | null;
  now: number;
  loading: boolean;
}) {
  if (available && windows.length > 0) {
    return (
      <div className="grid">
        {windows.map((w) => (
          <GaugeCard key={w.window} w={w} now={now} label={label} />
        ))}
      </div>
    );
  }
  return (
    <div className="card">
      <div className="sub">
        {loading
          ? "Loading…"
          : `${label} quota unavailable${degraded ? `: ${degraded}` : ""}.`}
      </div>
    </div>
  );
}

function MeterCard({ c }: { c: ClaudeConsumed }) {
  if (!c.available) {
    return (
      <div className="card">
        <div className="sub">
          Claude usage unavailable{c.degraded ? `: ${c.degraded}` : ""}.
        </div>
      </div>
    );
  }
  const rows: [string, number][] = [
    ["input", c.input_tokens],
    ["output", c.output_tokens],
    ["cache read", c.cache_read_input_tokens],
    ["cache write", c.cache_creation_input_tokens],
  ];
  const cost =
    c.estimated_cost_usd === null
      ? null
      : c.estimated_cost_usd.toLocaleString("en-US", {
          style: "currency",
          currency: "USD",
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
  return (
    <div className="card meter">
      <div className="big">{fmtNum(c.total_tokens)}</div>
      <div className="sub">
        tokens consumed · {fmtNum(c.events)} events · current session
      </div>
      {cost !== null && (
        <div className="cost">
          ~{cost}{" "}
          <span className="cost-note">
            est. spend{c.pricing_as_of ? ` · rates ${c.pricing_as_of}` : ""}
          </span>
        </div>
      )}
      <div className="breakdown">
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: "contents" }}>
            <span className="k">{k}</span>
            <span className="v">{fmtNum(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [down, setDown] = useState(false);
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    let alive = true;
    let es: EventSource | null = null;

    fetch(`${API}/api/quota`)
      .then((r) => r.json())
      .then((d: Snapshot) => {
        if (alive) {
          setSnap(d);
          setDown(false);
        }
      })
      .catch(() => {
        if (alive) setDown(true);
      });

    try {
      es = new EventSource(`${API}/api/events`);
      es.onmessage = (e: MessageEvent<string>) => {
        try {
          setSnap(JSON.parse(e.data) as Snapshot);
          setDown(false);
        } catch {
          /* ignore malformed frame */
        }
      };
    } catch {
      /* EventSource unavailable; the initial fetch + polling cover it */
    }

    const tick = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);

    return () => {
      alive = false;
      if (es) es.close();
      clearInterval(tick);
    };
  }, []);

  const updated = snap
    ? new Date(snap.generated_at * 1000).toLocaleTimeString()
    : "—";

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
        <span className="tag">radar</span>
        <span className="spacer" />
        <nav className="nav">
          <Link href="/" className="active">
            Dashboard
          </Link>
          <Link href="/watch">Watch</Link>
          <Link href="/timeline">Timeline</Link>
        </nav>
        <span className="updated" style={{ marginLeft: 14 }}>
          updated {updated}
        </span>
      </header>

      {down && !snap && (
        <div className="notice">
          Cannot reach the API at <code>{API}</code>. Start it with{" "}
          <code>
            uv --directory api run uvicorn missioncontrol.main:app --host
            127.0.0.1 --port 8787
          </code>
          .
        </div>
      )}

      <div className="section-title">Claude · rate-limit windows</div>
      <Gauges
        label="Claude"
        available={!!snap && snap.claude.quota_available}
        windows={snap?.claude.windows ?? []}
        degraded={snap?.claude.quota_degraded ?? null}
        now={now}
        loading={!snap}
      />

      <div className="section-title">Codex · rate-limit windows</div>
      <Gauges
        label="Codex"
        available={!!snap && snap.codex.available}
        windows={snap?.codex.windows ?? []}
        degraded={snap?.codex.degraded ?? null}
        now={now}
        loading={!snap}
      />

      <div className="section-title">Claude · consumed tokens</div>
      {snap ? (
        <MeterCard c={snap.claude} />
      ) : (
        <div className="card">
          <div className="sub">Loading…</div>
        </div>
      )}
    </main>
  );
}
