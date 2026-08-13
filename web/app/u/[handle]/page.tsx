"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Post, Profile, Unauthorized, getProfile } from "../../../lib/api";
import Avatar from "../../../components/Avatar";
import PostCard from "../../../components/PostCard";

type Tab = "posts" | "replies";

function joined(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

export default function ProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = use(params);
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [replies, setReplies] = useState<Post[]>([]);
  const [tab, setTab] = useState<Tab>("posts");
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    getProfile(handle)
      .then((data) => {
        setProfile(data.profile);
        setPosts(data.posts);
        setReplies(data.replies);
      })
      .catch((e) => {
        if (e instanceof Unauthorized) router.replace("/login");
        else setMissing(true);
      })
      .finally(() => setLoading(false));
  }, [handle, router]);

  // Escape closes it, because a full-bleed overlay with no visible chrome is a trap otherwise.
  useEffect(() => {
    if (!zoomed) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setZoomed(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [zoomed]);

  const shown = tab === "posts" ? posts : replies;

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
          <h1>{profile?.name ?? "Profile"}</h1>
          <button className="backlink" onClick={() => router.push("/")}>
            ← timeline
          </button>
        </header>

        {loading && <div className="empty"><p>Loading…</p></div>}

        {missing && (
          <div className="empty">
            <h2>Nobody lives here</h2>
            <p>
              There's no active resident with the handle <code>@{handle}</code>.
            </p>
          </div>
        )}

        {profile && (
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
                <Avatar
                  name={profile.name}
                  seed={profile.avatarSeed}
                  url={profile.avatarUrl}
                  size={76}
                />
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
        )}
      </main>

      <aside className="rail-r" />
    </div>
  );
}
