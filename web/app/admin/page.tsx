"use client";

/* The control room — this is the "we have to be mods" requirement, and it turned out
   not to need a moderation system. Posting rate is one number per character, so muting
   a character or slowing the whole world is editing a field. */

import { useCallback, useEffect, useState } from "react";
import { API } from "../../lib/api";

type Character = {
  id: string;
  handle: string;
  name: string;
  status: string;
  engagement_profile: { opens_per_day?: number } & Record<string, unknown>;
};

const STATUSES = ["draft", "active", "paused", "retired"];

export default function Admin() {
  const [token, setToken] = useState("");
  const [authed, setAuthed] = useState(false);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [note, setNote] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftContext, setDraftContext] = useState("");

  const headers = useCallback(
    () => ({ "content-type": "application/json", "x-admin-token": token }),
    [token],
  );

  const load = useCallback(async () => {
    let c, s;
    try {
      [c, s] = await Promise.all([
        fetch(`${API}/api/admin/characters`, { headers: headers() }),
        fetch(`${API}/api/admin/stats`, { headers: headers() }),
      ]);
    } catch {
      setNote("Can't reach the API. Is it running?");
      return false;
    }
    if (!c.ok) {
      setNote("That admin token doesn't match.");
      return false;
    }
    setCharacters((await c.json()).characters);
    // Stats are a nice-to-have; a 500 here must not blank the cast list.
    setStats(s.ok ? await s.json().catch(() => null) : null);
    return true;
  }, [headers]);

  useEffect(() => {
    if (authed) load();
  }, [authed, load]);

  async function unlock(e: React.FormEvent) {
    e.preventDefault();
    if (await load()) {
      setAuthed(true);
      setNote(null);
    }
  }

  async function patch(id: string, body: Record<string, unknown>) {
    await fetch(`${API}/api/admin/characters/${id}`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify(body),
    });
    load();
  }

  async function runTick() {
    setNote("Ticking…");
    const res = await fetch(`${API}/api/admin/tick`, { method: "POST", headers: headers() });
    const data = await res.json();
    if (!res.ok) {
      setNote("The tick failed. Check the worker logs.");
      return;
    }
    setNote(
      data.skipped
        ? "Another tick is already running."
        : `Tick ${data.tick_id ?? "?"}: ${data.turns_sent ?? 0} turns sent, ` +
          `${data.posts_written ?? 0} posts written.`,
    );
    load();
  }

  async function draftCharacter(e: React.FormEvent) {
    e.preventDefault();
    setNote("Drafting…");
    const res = await fetch(`${API}/api/admin/characters/draft`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ name: draftName, context: draftContext }),
    });
    if (!res.ok) {
      setNote(
        res.status === 503
          ? "Drafting needs a live provider. Set LLM_PROVIDER=anthropic."
          : "Couldn't draft that character.",
      );
      return;
    }
    const made = await res.json();
    setNote(`Drafted @${made.handle}. Review the card, then set it active.`);
    setDraftName("");
    setDraftContext("");
    load();
  }

  if (!authed) {
    return (
      <div className="gate">
        <form className="gate-card" onSubmit={unlock}>
          <h1>Control room</h1>
          <p>Character rates, world state, and the tick trigger.</p>
          <input
            className="field"
            type="password"
            value={token}
            autoFocus
            placeholder="Admin token"
            aria-label="Admin token"
            onChange={(e) => setToken(e.target.value)}
          />
          <button className="btn" disabled={!token}>Unlock</button>
          {note && <p className="err">{note}</p>}
        </form>
      </div>
    );
  }

  return (
    <div className="admin">
      <h1>Control room</h1>

      {stats && (
        <div className="statgrid">
          <div className="stat">
            <div className="stat-n">{stats.budget?.turns_per_day ?? 0}</div>
            <div className="stat-k">turns / day</div>
          </div>
          <div className="stat">
            <div className="stat-n">{stats.active}</div>
            <div className="stat-k">active</div>
          </div>
          <div className="stat">
            <div className="stat-n">{stats.posts}</div>
            <div className="stat-k">posts</div>
          </div>
          <div className="stat">
            <div className="stat-n">{stats.likes}</div>
            <div className="stat-k">likes</div>
          </div>
          <div className="stat">
            <div className="stat-n">{stats.open_batches}</div>
            <div className="stat-k">open batches</div>
          </div>
          <div className="stat">
            <div className="stat-n">{stats.blocked_headlines}</div>
            <div className="stat-k">headlines blocked</div>
          </div>
          <div className="stat">
            <div className="stat-n">{stats.usage?.failed_batches ?? 0}</div>
            <div className="stat-k">failed batches</div>
          </div>
          <div className="stat">
            <div className="stat-n">
              {((stats.usage?.cache_read_tokens ?? 0) / 1000).toFixed(1)}k
            </div>
            {/* Zero here is the only signal that prompt caching silently broke. */}
            <div className="stat-k">cache reads</div>
          </div>
          <div className="stat">
            <div className="stat-n">
              $
              {(
                ((stats.usage?.input_tokens ?? 0) * 3 +
                  (stats.usage?.output_tokens ?? 0) * 15 +
                  (stats.usage?.cache_read_tokens ?? 0) * 0.3) /
                1_000_000 /
                2
              ).toFixed(2)}
            </div>
            <div className="stat-k">spent (batched)</div>
          </div>
        </div>
      )}

      <h2>Advance the world</h2>
      <button className="btn" style={{ width: "auto", padding: "10px 18px" }} onClick={runTick}>
        Run one tick
      </button>
      {note && <p className="err" style={{ color: "var(--dim)" }}>{note}</p>}

      <h2>Cast — posting rate is the throttle</h2>
      {characters.map((c) => (
        <div className="crow" key={c.id}>
          <div>
            <div className="crow-name">{c.name}</div>
            <div className="crow-handle">@{c.handle}</div>
          </div>

          <input
            className="crow-input"
            type="number"
            step="0.1"
            min="0"
            aria-label={`Opens per day for ${c.name}`}
            defaultValue={c.engagement_profile?.opens_per_day ?? 1}
            onBlur={(e) => {
              // A cleared field used to PATCH 0, muting the character with no error.
              const next = Number(e.target.value);
              if (e.target.value.trim() === "" || Number.isNaN(next) || next < 0) {
                e.target.value = String(c.engagement_profile?.opens_per_day ?? 1);
                return;
              }
              patch(c.id, {
                engagement_profile: { ...c.engagement_profile, opens_per_day: next },
              });
            }}
          />

          <select
            className="crow-input"
            value={c.status}
            aria-label={`Status for ${c.name}`}
            onChange={(e) => patch(c.id, { status: e.target.value })}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      ))}

      <h2>Add a character</h2>
      <form onSubmit={draftCharacter}>
        <input
          className="field"
          value={draftName}
          placeholder="Name — e.g. Tony Soprano"
          aria-label="Character name"
          onChange={(e) => setDraftName(e.target.value)}
        />
        <input
          className="field"
          value={draftContext}
          placeholder="Context — e.g. mob boss, The Sopranos"
          aria-label="Character context"
          onChange={(e) => setDraftContext(e.target.value)}
        />
        <button className="btn" style={{ width: "auto", padding: "10px 18px" }} disabled={!draftName}>
          Draft card
        </button>
      </form>
    </div>
  );
}
