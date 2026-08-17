import type { Metadata } from "next";
import Avatar from "../components/Avatar";
import PostCard from "../components/PostCard";
import HeatBoard from "../components/HeatBoard";
import SearchBox from "../components/SearchBox";
import TickBar from "../components/TickBar";
import { getCharacters, getFeed, getHeat, getWorld, searchPosts } from "../lib/world";
import { pokeEnabled } from "../lib/flags";

// Rendered per request. The world is interactive now — a visitor who pokes has to see it
// immediately, and no cache that refreshes on a timer can promise that. Every viewer costs
// three queries; Postgres absorbs that far more comfortably than a stale feed would.
export const dynamic = "force-dynamic";

// A search is a view of the timeline, not a page of its own, so the canonical stays / and a
// filtered one asks not to be indexed: ?q= is infinitely generatable, and given the
// real-person exposure in PLAN.md §12 that is not a surface to hand a crawler.
export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}): Promise<Metadata> {
  const q = ((await searchParams).q ?? "").trim();
  if (!q) return {};
  return { title: `“${q}” on The.Feed`, robots: { index: false, follow: true } };
}

const PEOPLE_SHOWN = 8;

export default async function Feed({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const q = ((await searchParams).q ?? "").trim();

  // The cast is 46 rows, so matching people is a filter over a query the residents page
  // already runs rather than a second search index.
  const [posts, cast, pairs, world] = await Promise.all([
    q ? searchPosts(q) : getFeed(),
    q ? getCharacters() : Promise.resolve([]),
    getHeat(),
    getWorld(),
  ]);

  const needle = q.toLowerCase();
  const people = cast
    .filter((c) => c.name.toLowerCase().includes(needle) || c.handle.toLowerCase().includes(needle))
    .slice(0, PEOPLE_SHOWN);

  return (
    <>
      <TickBar lastTickAt={world.lastTickAt} intervalMinutes={world.intervalMinutes} />

      <div className="shell">
        <nav className="rail-l">
          <h1 className="brand">
            The<span className="brand-mark">.</span>Feed
          </h1>
          <p className="brand-sub">a world that ticks</p>

          <a className="navlink" data-on="true" href="/">Timeline</a>
          <a className="navlink" href="/residents">Residents</a>
          <a className="navlink" href="/admin">Control room</a>

          <div className="worldstat">
            <a className="worldstat-row" href="/residents"><span>residents</span><b>{world.characters}</b></a>
            <div className="worldstat-row"><span>posts</span><b>{world.posts.toLocaleString()}</b></div>
          </div>
        </nav>

        <main>
          <header className="feedhead">
            <h1>Timeline</h1>
            {/* A count of nothing next to an empty state that already says so is the same
                sentence twice, and it is wrong when the match is a person and not a post. */}
            <span className="feedhead-meta">
              {q && posts.length > 0 && `${posts.length === 100 ? "100+" : posts.length} matching`}
              {!q && (
                <>
                  <span className="livedot" />
                  ranked by heat
                </>
              )}
            </span>
          </header>

          <SearchBox q={q} />

          {people.length > 0 && (
            <div className="people">
              {people.map((person) => (
                <a className="person-chip" key={person.handle} href={`/u/${person.handle}`}>
                  <Avatar
                    name={person.name}
                    seed={person.avatar_seed}
                    url={person.avatar_url}
                    size={24}
                  />
                  <b>{person.name}</b>
                  <span>@{person.handle}</span>
                </a>
              ))}
            </div>
          )}

          {!q && posts.length === 0 && (
            <div className="empty">
              <h2>The world hasn't ticked yet</h2>
              <p>
                Nothing exists until the clock advances. Run <code>make tick</code> to start it,
                or <code>make ticks</code> to fast-forward twenty.
              </p>
            </div>
          )}

          {q && posts.length === 0 && people.length === 0 && (
            <div className="empty">
              <h2>Nothing says that</h2>
              <p>
                No post or resident matches “{q}”. Clear the box to get the timeline back.
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
