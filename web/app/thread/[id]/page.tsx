import { notFound } from "next/navigation";
import PostCard from "../../../components/PostCard";
import { getFeed, getThread } from "../../../lib/world";

// Per-path cache key, so this and /u/[handle] are the only routes where an attacker can
// force cold renders on demand. That is what the rate limiter in middleware.ts is for.
export const revalidate = 900;

// Threads are unbounded, so this prerenders the ones actually reachable from the timeline
// and heat board. A thread outside that set renders on demand and is not cached — which is
// precisely the surface the per-IP limiter in middleware.ts covers. DEPLOY.md §4.
export async function generateStaticParams() {
  return (await getFeed(100)).map((p) => ({ id: p.id }));
}

export default async function Thread({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const posts = await getThread(id);
  if (posts.length === 0) notFound();

  const root = posts.find((p) => !p.parentId) ?? posts[0];
  const replies = posts.filter((p) => p.id !== root.id);

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
          <a className="backlink" href="/">← timeline</a>
        </header>

        <PostCard post={root} index={0} linked={false} />

        {/* Counts every descendant of the root, so it can exceed the root's direct
            reply count. */}
        {replies.length > 0 && (
          <p className="thread-count">{replies.length} in this thread</p>
        )}

        {replies.map((post, i) => (
          <PostCard key={post.id} post={post} index={i + 1} linked={false} isReply />
        ))}

        {replies.length === 0 && (
          <div className="empty">
            <p>No replies yet. Nobody has opened the app since this went up.</p>
          </div>
        )}
      </main>

      <aside className="rail-r" />
    </div>
  );
}
