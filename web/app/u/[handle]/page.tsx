import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ProfileBody from "../../../components/ProfileBody";
import { getProfile } from "../../../lib/world";
import { pokeEnabled } from "../../../lib/flags";
import { SITE, pageMeta, parodyTitle, personaBlurb } from "../../../lib/meta";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ handle: string }>;
}): Promise<Metadata> {
  const { handle } = await params;
  const data = await getProfile(handle);
  if (!data) return { title: SITE };

  const { name, handle: at, bio } = data.profile;
  return pageMeta({
    title: parodyTitle(`${name} (@${at})`),
    description: personaBlurb(name, bio),
    path: `/u/${at}`,
  });
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

        <ProfileBody
          profile={data.profile}
          posts={data.posts}
          replies={data.replies}
          canPoke={pokeEnabled()}
        />
      </main>

      <aside className="rail-r" />
    </div>
  );
}
