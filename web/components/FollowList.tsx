"use client";

/* The two directions are one screen with one word changed, and X switches between them
   with tabs rather than a back-and-forward, so both pages render this. */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Person, Profile, Unauthorized, getFollowers, getFollowing, getProfile } from "../lib/api";
import Avatar from "./Avatar";

export default function FollowList({
  handle,
  direction,
}: {
  handle: string;
  direction: "followers" | "following";
}) {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [people, setPeople] = useState<Person[] | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const load = direction === "followers" ? getFollowers : getFollowing;
    Promise.all([getProfile(handle), load(handle)])
      .then(([p, list]) => {
        setProfile(p.profile);
        setPeople(list.people);
      })
      .catch((e) => {
        if (e instanceof Unauthorized) router.replace("/login");
        else setMissing(true);
      });
  }, [handle, direction, router]);

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
            <h1>{profile?.name ?? handle}</h1>
            <p className="profile-handle">@{handle}</p>
          </div>
          <button className="backlink" onClick={() => router.push(`/u/${handle}`)}>
            ← profile
          </button>
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

        {missing && (
          <div className="empty">
            <h2>Nobody lives here</h2>
            <p>There's no active resident with the handle <code>@{handle}</code>.</p>
          </div>
        )}

        {!missing && people === null && <div className="empty"><p>Loading…</p></div>}

        {people?.map((person) => (
          <a className="resident" key={person.handle} href={`/u/${person.handle}`}>
            <Avatar name={person.name} seed={person.avatarSeed} url={person.avatarUrl} size={44} />
            <div className="resident-id">
              <div className="resident-name">{person.name}</div>
              <div className="resident-handle">@{person.handle}</div>
              {person.bio && <p className="resident-bio">{person.bio}</p>}
            </div>
          </a>
        ))}

        {people?.length === 0 && (
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
