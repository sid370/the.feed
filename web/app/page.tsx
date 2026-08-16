import PostCard from "../components/PostCard";
import HeatBoard from "../components/HeatBoard";
import TickBar from "../components/TickBar";
import { getFeed, getHeat, getWorld } from "../lib/world";

// Half a tick. Every visitor sees the identical feed, so this is what turns an unbounded
// number of viewers into two cold renders an hour. Half rather than the whole interval
// because Actions schedules drift, so a visitor sees a new world within thirty minutes of it
// existing. Keep this at half of TICK_INTERVAL_MINUTES — it also sets the KV write rate.
export const revalidate = 1800;

export default async function Feed() {
  const [posts, pairs, world] = await Promise.all([getFeed(), getHeat(), getWorld()]);

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
            <span className="feedhead-meta">
              <span className="livedot" />
              ranked by heat
            </span>
          </header>

          {posts.length === 0 && (
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
