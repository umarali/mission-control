"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8787";

type Turn = { role: string; text: string; tools: string[]; ts: string | null };
type Transcript = {
  available: boolean;
  agent: string;
  turns: Turn[];
  session_id: string | null;
  degraded: string | null;
};

type Agent = "claude" | "codex";

function fmtTime(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString();
}

function roleClass(role: string): string {
  if (role === "user") return "user";
  if (role === "assistant") return "assistant";
  if (role === "tool") return "tool";
  return "other";
}

function TurnRow({ t }: { t: Turn }) {
  return (
    <div className={`turn ${roleClass(t.role)}`}>
      <div className="turn-head">
        <span className="role">{t.role}</span>
        {t.ts && <span className="turn-ts">{fmtTime(t.ts)}</span>}
      </div>
      {t.text && <div className="turn-text">{t.text}</div>}
      {t.tools.length > 0 && (
        <div className="tools">
          {t.tools.map((tool, i) => (
            <span key={`${tool}-${i}`} className="toolchip">
              {tool}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Watch() {
  const [agent, setAgent] = useState<Agent>("claude");
  const [data, setData] = useState<Transcript | null>(null);
  const [down, setDown] = useState(false);
  const [jumpResult, setJumpResult] = useState<{
    agent: Agent;
    command: string;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/api/transcript?agent=${agent}&limit=200`)
      .then((r) => r.json())
      .then((d: Transcript) => {
        if (alive) {
          setData(d);
          setDown(false);
        }
      })
      .catch(() => {
        if (alive) setDown(true);
      });
    return () => {
      alive = false;
    };
  }, [agent]);

  // Derived (not stored) so we never setState directly inside the effect.
  const loading = !down && (data === null || data.agent !== agent);

  // Jump-to-agent: fetch the per-session token, then POST it to the guarded action endpoint.
  async function doJump() {
    if (!data?.session_id) return;
    try {
      const { token } = await fetch(`${API}/api/session`).then((r) => r.json());
      const res = await fetch(`${API}/api/jump`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-MC-Session": token },
        body: JSON.stringify({ agent, session_id: data.session_id }),
      }).then((r) => r.json());
      if (typeof res.command === "string")
        setJumpResult({ agent, command: res.command });
    } catch {
      /* leave any prior result; the API-down notice covers connectivity */
    }
  }

  const jumpCmd =
    jumpResult && jumpResult.agent === agent ? jumpResult.command : null;

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
        <span className="tag">watch</span>
        <span className="spacer" />
        <nav className="nav">
          <Link href="/">Dashboard</Link>
          <Link href="/watch" className="active">
            Watch
          </Link>
          <Link href="/timeline">Timeline</Link>
        </nav>
      </header>

      <div className="toggle">
        <button
          className={agent === "claude" ? "on" : ""}
          onClick={() => setAgent("claude")}
          type="button"
        >
          Claude
        </button>
        <button
          className={agent === "codex" ? "on" : ""}
          onClick={() => setAgent("codex")}
          type="button"
        >
          Codex
        </button>
        {!loading && data?.session_id && (
          <span className="session">
            session {data.session_id.slice(0, 12)}
          </span>
        )}
        {!loading && data?.available && data?.session_id && (
          <button className="jump" onClick={doJump} type="button">
            Jump to agent
          </button>
        )}
      </div>

      {jumpCmd && (
        <div className="jumpcmd">
          Resume this session: <code>{jumpCmd}</code>
        </div>
      )}

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

      {!down && loading && (
        <div className="card">
          <div className="sub">Loading transcript…</div>
        </div>
      )}

      {!down && !loading && data && !data.available && (
        <div className="card">
          <div className="sub">
            No {agent} transcript{data.degraded ? `: ${data.degraded}` : ""}.
          </div>
        </div>
      )}

      {!down && !loading && data && data.available && (
        <div className="feed">
          {data.turns.map((t, i) => (
            <TurnRow key={i} t={t} />
          ))}
        </div>
      )}
    </main>
  );
}
