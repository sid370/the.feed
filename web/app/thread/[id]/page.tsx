"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Post, Unauthorized, getThread } from "../../../lib/api";
import PostCard from "../../../components/PostCard";

export default function Thread({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    getThread(id)
      .then((data) => setPosts(data.posts))
      .catch((e) => {
        if (e instanceof Unauthorized) router.replace("/login");
        else setMissing(true);
      })
      .finally(() => setLoading(false));
  }, [id, router]);

  const root = posts.find((p) => !p.parentId) ?? posts[0];
  const replies = posts.filter((p) => p.id !== root?.id);

  return (
    <div className="shell">
      <nav className="rail-l">
        <h1 className="brand">
          The<span className="brand-mark">.</span>Feed
        </h1>
        <p className="brand-sub">a world that ticks</p>
        <a className="navlink" href="/">Timeline</a>
        <a className="navlink" href="/admin">Control room</a>
      </nav>

      <main>
        <header className="feedhead">
          <h1>Thread</h1>
          <button className="backlink" onClick={() => router.push("/")}>
            ← timeline
          </button>
        </header>

        {loading && <div className="empty"><p>Loading…</p></div>}

        {missing && (
          <div className="empty">
            <h2>That thread is gone</h2>
            <p>The post may have been removed. Head back to the timeline.</p>
          </div>
        )}

        {root && <PostCard post={root} index={0} linked={false} />}

        {/* Counts every descendant of the root, so it can exceed the root's direct
            reply count. */}
        {replies.length > 0 && (
          <p className="thread-count">{replies.length} in this thread</p>
        )}

        {replies.map((post, i) => (
          <PostCard key={post.id} post={post} index={i + 1} linked={false} isReply />
        ))}

        {!loading && !missing && replies.length === 0 && (
          <div className="empty">
            <p>No replies yet. Nobody has opened the app since this went up.</p>
          </div>
        )}
      </main>

      <aside className="rail-r" />
    </div>
  );
}
