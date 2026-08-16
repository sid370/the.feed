import Avatar from "../../components/Avatar";
import { getCharacters } from "../../lib/world";

// Parameterless, so this collapses to a single cache entry — there is no path to vary and
// therefore no way to force a cold render. DEPLOY.md §4.
export const revalidate = false;

export default async function Residents() {
  const cast = await getCharacters();

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

        {cast.length === 0 && (
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
