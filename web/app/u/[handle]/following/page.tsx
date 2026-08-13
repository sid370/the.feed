"use client";

import { use } from "react";
import FollowList from "../../../../components/FollowList";

export default function Following({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = use(params);
  return <FollowList handle={handle} direction="following" />;
}
