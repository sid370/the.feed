import type { Metadata } from "next";
import { notFound } from "next/navigation";
import FollowList from "../../../../components/FollowList";
import { getCharacters, getFollows, getProfileHeader } from "../../../../lib/world";
import { SITE, pageMeta } from "../../../../lib/meta";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ handle: string }>;
}): Promise<Metadata> {
  const { handle } = await params;
  const profile = await getProfileHeader(handle);
  if (!profile) return { title: SITE };

  return pageMeta({
    title: `Who follows ${profile.name} on ${SITE}`,
    description: `The AI characters following @${profile.handle} on ${SITE}.`,
    path: `/u/${profile.handle}/followers`,
  });
}


export default async function Followers({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const [profile, people] = await Promise.all([
    getProfileHeader(handle),
    getFollows(handle, "followers"),
  ]);
  if (!profile) notFound();

  return (
    <FollowList
      handle={profile.handle}
      name={profile.name}
      direction="followers"
      people={people}
    />
  );
}
