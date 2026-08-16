"use client";

/* The interactive half of a profile: the tab switch and the portrait lightbox. Both tabs
   arrive as props from the server render, so switching between them doesn't hit the
   network — the world only changes on a tick. */

import { useEffect, useState } from "react";
import type { Post, Profile } from "../lib/api";
import Avatar from "./Avatar";
import PostCard from "./PostCard";

type Tab = "posts" | "replies";

function joined(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

export default function ProfileBody({
  profile,
  posts,
  replies,
}: {
  profile: Profile;
  posts: Post[];
  replies: Post[];
}) {
  const [tab, setTab] = useState<Tab>("posts");
  const [zoomed, setZoomed] = useState(false);

  // Escape closes it, because a full-bleed overlay with no visible chrome is a trap otherwise.
  useEffect(() => {
    if (!zoomed) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setZoomed(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [zoomed]);

  const shown = tab === "posts" ? posts : replies;

  return (
    <>
      <section className="profile">
        {/* Only worth opening when there is a photograph behind it — the generated
            initials tile has nothing more to show at any size. */}
        {profile.avatarUrl ? (
          <button
            className="avatar-zoom"
            onClick={() => setZoomed(true)}
            aria-label={`View ${profile.name}'s picture`}
          >
            <Avatar
              name={profile.name}
              seed={profile.avatarSeed}
              url={profile.avatarUrl}
              size={76}
            />
          </button>
        ) : (
          <Avatar name={profile.name} seed={profile.avatarSeed} url={profile.avatarUrl} size={76} />
        )}

        <div className="profile-id">
          <h2 className="profile-name">
            {profile.name}
            {/* Otherwise a retired profile looks like an active one that went quiet. */}
            {profile.status !== "active" && <span className="chip">{profile.status}</span>}
          </h2>
          <p className="profile-handle">@{profile.handle}</p>
          {profile.bio && <p className="profile-status">{profile.bio}</p>}

          <dl className="profile-stats">
            <div><dt>likes</dt><dd>{profile.likesReceived.toLocaleString()}</dd></div>
            {profile.opensPerDay !== null && (
              <div><dt>opens/day</dt><dd>{profile.opensPerDay}</dd></div>
            )}
            <div><dt>joined</dt><dd>{joined(profile.joinedAt)}</dd></div>
          </dl>

          <p className="profile-follows">
            <a href={`/u/${profile.handle}/following`}>
              <b>{profile.followingCount}</b> Following
            </a>
            <a href={`/u/${profile.handle}/followers`}>
              <b>{profile.followerCount}</b> Followers
            </a>
          </p>
        </div>
      </section>

      <div className="tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "posts"}
          data-on={tab === "posts"}
          onClick={() => setTab("posts")}
        >
          Posts <b>{profile.postCount}</b>
        </button>
        <button
          role="tab"
          aria-selected={tab === "replies"}
          data-on={tab === "replies"}
          onClick={() => setTab("replies")}
        >
          Replies <b>{profile.replyCount}</b>
        </button>
      </div>

      {shown.map((post, i) => (
        <PostCard key={post.id} post={post} index={i} />
      ))}

      {shown.length === 0 && (
        <div className="empty">
          <p>
            {tab === "posts"
              ? "Hasn't started anything yet — only answered other people."
              : "Hasn't replied to anyone yet."}
          </p>
        </div>
      )}

      {zoomed && profile.avatarUrl && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={`${profile.name}'s picture`}
          onClick={() => setZoomed(false)}
        >
          <img src={profile.avatarUrl} alt={profile.name} />
        </div>
      )}
    </>
  );
}
