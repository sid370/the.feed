import { notFound } from "next/navigation";
import FollowList from "../../../../components/FollowList";
import { getCharacters, getFollows, getProfileHeader } from "../../../../lib/world";

export const revalidate = false;

// One entry per resident, so every follow list is warm. An empty array here does NOT give
// on-demand ISR — it silently leaves the route rendering on every request.
export async function generateStaticParams() {
  return (await getCharacters()).map((c) => ({ handle: c.handle }));
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
