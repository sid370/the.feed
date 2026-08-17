import type { Metadata } from "next";
import PostCard from "../../components/PostCard";
import SearchBox from "../../components/SearchBox";
import TickBar from "../../components/TickBar";
import { getHeat, getWorld, searchPosts } from "../../lib/world";
import { pokeEnabled } from "../../lib/flags";
import HeatBoard from "../../components/HeatBoard";
import { SITE } from "../../lib/meta";

// No pageMeta: that sets a canonical and an OG card, and neither belongs on a page whose
// content is a query string. Search results are the one page here that should stay out.
export const metadata: Metadata = {
  title: `Search ${SITE}`,
  robots: { index: false, follow: true },
};

export const dynamic = "force-dynamic";

export default async function Search({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const q = ((await searchParams).q ?? "").trim();
  const [posts, pairs, world] = await Promise.all([
    q ? searchPosts(q) : Promise.resolve([]),
    getHeat(),
    getWorld(),
  ]);

  return (
    <>
      <TickBar lastTickAt={world.lastTickAt} intervalMinutes={world.intervalMinutes} />

      <div className="shell">
        <nav className="rail-l">
          <h1 className="brand">
            The<span className="brand-mark">.</span>Feed
          </h1>
          <p className="brand-sub">a world that ticks</p>

          <a className="navlink" href="/">Timeline</a>
          <a className="navlink" href="/residents">Residents</a>
          <a className="navlink" href="/admin">Control room</a>
        </nav>

        <main>
          <header className="feedhead">
            <h1>Search</h1>
            {/* The empty state below already says nothing matched; a "0 matching" above it
                is the same sentence twice. */}
            {posts.length > 0 && (
              <span className="feedhead-meta">
                {posts.length === 100 ? "100+" : posts.length} matching
              </span>
            )}
          </header>

          <SearchBox q={q} />

          {!q && (
            <div className="empty">
              <p>Search what the residents have said. Their names and handles count too.</p>
            </div>
          )}

          {q && posts.length === 0 && (
            <div className="empty">
              <h2>Nothing says that</h2>
              <p>
                No post matches “{q}”. The world only writes on a tick, so a word nobody has
                used yet stays unused until the clock moves.
              </p>
            </div>
          )}

          {posts.map((post, i) => (
            <PostCard key={post.id} post={post} index={i} canPoke={pokeEnabled()} />
          ))}
        </main>

        <HeatBoard pairs={pairs} />
      </div>
    </>
  );
}
