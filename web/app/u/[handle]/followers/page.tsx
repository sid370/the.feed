"use client";

import { use } from "react";
import FollowList from "../../../../components/FollowList";

export default function Followers({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = use(params);
  return <FollowList handle={handle} direction="followers" />;
}
