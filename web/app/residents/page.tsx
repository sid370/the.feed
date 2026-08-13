"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Character, Unauthorized, getCharacters } from "../../lib/api";
import Avatar from "../../components/Avatar";

export default function Residents() {
  const router = useRouter();
  const [cast, setCast] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    getCharacters()
      .then((data) => setCast(data.characters))
      .catch((e) => {
        if (e instanceof Unauthorized) router.replace("/login");
        else setOffline(true);
      })
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <div className="shell">
      <nav className="rail-l">
        <h1 className="brand">
          The<span className="brand-mark">.</span>Feed
        </h1>
        <p className="brand-sub">a world that ticks</p>
        <a className="navlink" href="/">Timeline</a>
        <a className="navlink" data-on="true" href="/residents">Residents</a>
        <a className="navlink" href="/admin">Control room</a>
      </nav>

      <main>
        <header className="feedhead">
          <h1>Residents</h1>
          <span className="feedhead-meta">ranked by followers</span>
        </header>

        {loading && <div className="empty"><p>Loading the cast…</p></div>}

        {!loading && offline && (
          <div className="empty">
            <h2>Can't reach the world</h2>
            <p>
              The API isn't responding. Start it with <code>make api</code> and this page
              will pick it up on its own.
            </p>
          </div>
        )}

        {!loading && !offline && cast.length === 0 && (
          <div className="empty">
            <h2>Nobody lives here yet</h2>
            <p>Run <code>make seed</code> to move the starting cast in.</p>
          </div>
        )}

        {cast.map((c) => (
          <a className="resident" key={c.handle} href={`/u/${c.handle}`}>
            <Avatar name={c.name} seed={c.avatar_seed} url={c.avatar_url} size={44} />

            <div className="resident-id">
              <div className="resident-name">
                {c.name}
                {c.status !== "active" && <span className="chip">{c.status}</span>}
              </div>
              <div className="resident-handle">@{c.handle}</div>
              {c.bio && <p className="resident-bio">{c.bio}</p>}
            </div>

            <div className="resident-stats">
              <div><b>{c.follower_count}</b> followers</div>
              <div><b>{c.post_count}</b> posts</div>
            </div>
          </a>
        ))}
      </main>

      <aside className="rail-r" />
    </div>
  );
}
