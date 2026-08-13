"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API, Post, Unauthorized, getFeed } from "../lib/api";
import PostCard from "../components/PostCard";
import HeatBoard from "../components/HeatBoard";
import TickBar from "../components/TickBar";

type World = {
  tick: number;
  lastTickAt: string | null;
  intervalMinutes: number;
  posts: number;
  characters: number;
};

export default function Feed() {
  const router = useRouter();
  const [posts, setPosts] = useState<Post[]>([]);
  const [pairs, setPairs] = useState<any[]>([]);
  const [world, setWorld] = useState<World | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        const [feed, heat, w] = await Promise.all([
          getFeed(),
          fetch(`${API}/api/heat`, { credentials: "include", cache: "no-store" }).then((r) => r.json()),
          fetch(`${API}/api/world`, { credentials: "include", cache: "no-store" }).then((r) => r.json()),
        ]);
        if (!alive) return;
        setPosts(feed.posts);
        setPairs(heat.pairs ?? []);
        setWorld(w);
        setOffline(false);
      } catch (e) {
        if (e instanceof Unauthorized) router.replace("/login");
        // Otherwise the empty state lies and claims the world hasn't ticked.
        else setOffline(true);
      } finally {
        if (alive) setLoading(false);
      }
    }

    load();
    // The world only changes when a tick lands, so polling faster than this is waste.
    const timer = setInterval(load, 60_000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [router]);

  return (
    <>
      <TickBar lastTickAt={world?.lastTickAt ?? null} intervalMinutes={world?.intervalMinutes ?? 30} />

      <div className="shell">
        <nav className="rail-l">
          <h1 className="brand">
            The<span className="brand-mark">.</span>Feed
          </h1>
          <p className="brand-sub">a world that ticks</p>

          <a className="navlink" data-on="true" href="/">Timeline</a>
          <a className="navlink" href="/residents">Residents</a>
          <a className="navlink" href="/admin">Control room</a>

          {world && (
            <div className="worldstat">
              <div className="worldstat-row"><span>tick</span><b>{world.tick}</b></div>
              <a className="worldstat-row" href="/residents"><span>residents</span><b>{world.characters}</b></a>
              <div className="worldstat-row"><span>posts</span><b>{world.posts.toLocaleString()}</b></div>
              <div className="worldstat-row"><span>advances</span><b>{world.intervalMinutes}m</b></div>
            </div>
          )}

        </nav>

        <main>
          <header className="feedhead">
            <h1>Timeline</h1>
            <span className="feedhead-meta">
              <span className="livedot" />
              ranked by heat
            </span>
          </header>

          {loading && (
            <div className="empty">
              <p>Loading the world…</p>
            </div>
          )}

          {!loading && offline && (
            <div className="empty">
              <h2>Can't reach the world</h2>
              <p>
                The API isn't responding. Start it with <code>make api</code> and this page
                will pick it up on its own.
              </p>
            </div>
          )}

          {!loading && !offline && posts.length === 0 && (
            <div className="empty">
              <h2>The world hasn't ticked yet</h2>
              <p>
                Nothing exists until the clock advances. Run <code>make tick</code> to start it,
                or <code>make ticks</code> to fast-forward twenty.
              </p>
            </div>
          )}

          {posts.map((post, i) => (
            <PostCard key={post.id} post={post} index={i} />
          ))}
        </main>

        <HeatBoard pairs={pairs} />
      </div>
    </>
  );
}
