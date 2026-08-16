import { notFound } from "next/navigation";
import FollowList from "../../../../components/FollowList";
import { getCharacters, getFollows, getProfileHeader } from "../../../../lib/world";

export const dynamic = "force-dynamic";


export default async function Following({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const [profile, people] = await Promise.all([
    getProfileHeader(handle),
    getFollows(handle, "following"),
  ]);
  if (!profile) notFound();

  return (
    <FollowList
      handle={profile.handle}
      name={profile.name}
      direction="following"
      people={people}
    />
  );
}
