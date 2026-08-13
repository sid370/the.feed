"use client";

import { useState } from "react";
import { avatarColor, initials } from "../lib/api";

export default function Avatar({
  name,
  seed,
  url,
  size = 40,
}: {
  name: string;
  seed: string;
  url?: string | null;
  size?: number;
}) {
  // A moved file or a dead external URL must not leave a hole where a face goes.
  const [broken, setBroken] = useState(false);
  const box = { width: size, height: size, background: avatarColor(seed) };

  if (url && !broken) {
    return (
      <img className="avatar" style={box} src={url} alt="" onError={() => setBroken(true)} />
    );
  }

  return (
    <span className="avatar" style={{ ...box, fontSize: Math.round(size / 3) }}>
      {initials(name)}
    </span>
  );
}
