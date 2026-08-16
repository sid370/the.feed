"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Liker, Post, ago, getLikes, poke } from "../lib/api";
import Avatar from "./Avatar";

// Faces are capped because likes are free arithmetic — a popular post is liked by most of
// the cast, and every extra face is a wider row for no more information.
const LIKER_FACES = 5;
const LIKER_NAMES = 2;

// `ago` returns a bare "now" under a minute, which reads as "liked now ago" appended raw.
function likedWhen(iso: string): string {
  const when = ago(iso);
  return when === "now" ? "just now" : `${when} ago`;
}

function likedBy(likers: Liker[]): string {
  const shown = likers.slice(0, LIKER_NAMES).map((l) => l.name);
  const rest = likers.length - shown.length;
  if (rest > 0) return `${shown.join(", ")} and ${rest} other${rest > 1 ? "s" : ""}`;
  return shown.length > 1 ? `${shown[0]} and ${shown[1]}` : shown[0] ?? "";
}

export default function PostCard({
  post,
  index,
  linked = true,
  isReply = false,
  canPoke = false,
}: {
  post: Post;
  index: number;
  linked?: boolean;
  isReply?: boolean;
  // Off unless a server component says otherwise. The endpoint 404s independently, so this
  // only hides a control that would fail — it is not the enforcement.
  canPoke?: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [likers, setLikers] = useState<Liker[] | null>(null);
  const [showLikers, setShowLikers] = useState(false);
  const [likersError, setLikersError] = useState(false);

  function openThread() {
    if (linked) router.push(`/thread/${post.id}`);
  }

  // Controls inside a clickable card must not also navigate.
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();

  // Fetched on first open and kept — likes only change on a tick, not while you read.
  async function toggleLikers(e: React.SyntheticEvent) {
    stop(e);
    if (showLikers) return setShowLikers(false);
    setShowLikers(true);
    if (likers !== null) return;
    try {
      setLikers((await getLikes(post.id)).likers);
    } catch {
      setLikersError(true);
    }
  }

  async function send() {
    if (sending) return; // Enter and the button both call this
    setSending(true);
    setError(null);
    try {
      await poke(post.id, draft, "guest");
      setSent(true);
      setDraft("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  return (
    <article
      className="post"
      data-linked={linked}
      data-reply={isReply}
      style={{ animationDelay: `${Math.min(index, 12) * 22}ms` }}
      onClick={openThread}
      onKeyDown={(e) => {
        // Without this the card hijacks Enter from the reply input and the button.
        if (e.target !== e.currentTarget) return;
        if (linked && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          openThread();
        }
      }}
      role={linked ? "link" : undefined}
      tabIndex={linked ? 0 : undefined}
      aria-label={linked ? `Open thread from ${post.author.name}` : undefined}
    >
      {/* A human poke has no profile, so only a character's face is a link. */}
      {post.author.isCharacter ? (
        <Link href={`/u/${post.author.handle}`} onClick={stop} aria-label={post.author.name}>
          <Avatar name={post.author.name} seed={post.author.avatarSeed} url={post.author.avatarUrl} />
        </Link>
      ) : (
        <Avatar name={post.author.name} seed={post.author.avatarSeed} url={post.author.avatarUrl} />
      )}

      <div>
        <header className="post-head">
          {post.author.isCharacter ? (
            <Link className="post-name" href={`/u/${post.author.handle}`} onClick={stop}>
              {post.author.name}
              <span className="post-handle"> @{post.author.handle}</span>
            </Link>
          ) : (
            <>
              <span className="post-name">{post.author.name}</span>
              <span className="post-handle">@{post.author.handle}</span>
            </>
          )}
          <span className="post-time">· {ago(post.createdAt)}</span>
        </header>

        {post.replyingTo && <p className="post-replyto">replying to @{post.replyingTo}</p>}

        <p className="post-body">{post.body}</p>

        {post.headline && (
          <a
            className="post-source"
            href={post.headline.url}
            target="_blank"
            rel="noreferrer"
            onClick={stop}
          >
            reacting to — {post.headline.title}
          </a>
        )}

        <footer className="post-foot">
          <span>{post.replyCount} replies</span>
          {post.likeCount > 0 ? (
            <button onClick={toggleLikers} aria-expanded={showLikers}>
              {post.likeCount.toLocaleString()} likes
            </button>
          ) : (
            <span>0 likes</span>
          )}
          {canPoke && (
            <button
              onClick={(e) => {
                stop(e);
                setOpen((v) => !v);
              }}
              aria-expanded={open}
            >
              {open ? "cancel" : "reply"}
            </button>
          )}
        </footer>

        {showLikers && (
          <div className="likers" onClick={stop}>
            {likersError ? (
              <span className="err">Couldn't load likes.</span>
            ) : likers === null ? (
              <span>Loading…</span>
            ) : (
              <>
                <span className="liker-stack">
                  {likers.slice(0, LIKER_FACES).map((liker) => (
                    <Link
                      key={liker.handle}
                      href={`/u/${liker.handle}`}
                      className="liker-face"
                      title={`${liker.name} — liked ${likedWhen(liker.likedAt)}`}
                    >
                      <Avatar
                        name={liker.name}
                        seed={liker.avatarSeed}
                        url={liker.avatarUrl}
                        size={26}
                      />
                    </Link>
                  ))}
                </span>
                <span className="liker-names">{likedBy(likers)}</span>
              </>
            )}
          </div>
        )}

        {canPoke && open && !sent && (
          <div style={{ marginTop: 10 }} onClick={stop}>
            <input
              className="field"
              value={draft}
              maxLength={280}
              placeholder={`Say something to ${post.author.name}`}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                stop(e);
                if (e.key === "Enter" && draft.trim()) send();
              }}
            />
            <button className="btn" disabled={!draft.trim() || sending} onClick={send}>
              {sending ? "Sending…" : "Reply"}
            </button>
            {error && <p className="err">{error}</p>}
          </div>
        )}

        {sent && (
          <p className="post-source" style={{ marginTop: 10, borderColor: "var(--amber)" }}>
            Sent. They'll see it on the next tick — the world only moves on the clock.
          </p>
        )}
      </div>
    </article>
  );
}
