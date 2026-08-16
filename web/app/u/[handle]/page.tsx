import { notFound } from "next/navigation";
import ProfileBody from "../../../components/ProfileBody";
import { getCharacters, getProfile } from "../../../lib/world";

export const revalidate = 900;

// The cast is small and known at build, so every profile is prerendered rather than left to
// be generated on first visit. That removes the one read surface where an attacker could
// force cold renders by walking handles — there is nothing left to warm. DEPLOY.md §4.
export async function generateStaticParams() {
  return (await getCharacters()).map((c) => ({ handle: c.handle }));
}

export default async function ProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const data = await getProfile(handle);
  if (!data) notFound();

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
          <h1>{data.profile.name}</h1>
          <a className="backlink" href="/">← timeline</a>
        </header>

        <ProfileBody profile={data.profile} posts={data.posts} replies={data.replies} />
      </main>

      <aside className="rail-r" />
    </div>
  );
}
