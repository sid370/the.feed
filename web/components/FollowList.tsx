/* The two directions are one screen with one word changed, and X switches between them
   with tabs rather than a back-and-forward, so both pages render this. */

import type { Person } from "../lib/api";
import Avatar from "./Avatar";

export default function FollowList({
  handle,
  name,
  direction,
  people,
}: {
  handle: string;
  name: string;
  direction: "followers" | "following";
  people: Person[];
}) {
  return (
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
          <div>
            <h1>{name}</h1>
            <p className="profile-handle">@{handle}</p>
          </div>
          <a className="backlink" href={`/u/${handle}`}>← profile</a>
        </header>

        <div className="tabs" role="tablist">
          <a
            role="tab"
            aria-selected={direction === "followers"}
            data-on={direction === "followers"}
            href={`/u/${handle}/followers`}
          >
            Followers
          </a>
          <a
            role="tab"
            aria-selected={direction === "following"}
            data-on={direction === "following"}
            href={`/u/${handle}/following`}
          >
            Following
          </a>
        </div>

        {people.map((person) => (
          <a className="resident" key={person.handle} href={`/u/${person.handle}`}>
            <Avatar name={person.name} seed={person.avatarSeed} url={person.avatarUrl} size={44} />
            <div className="resident-id">
              <div className="resident-name">{person.name}</div>
              <div className="resident-handle">@{person.handle}</div>
              {person.bio && <p className="resident-bio">{person.bio}</p>}
            </div>
          </a>
        ))}

        {people.length === 0 && (
          <div className="empty">
            <p>
              {direction === "followers"
                ? "Nobody follows them yet."
                : "They don't follow anyone yet."}
            </p>
          </div>
        )}
      </main>

      <aside className="rail-r" />
    </div>
  );
}
