"use client";

import { useEffect, useState } from "react";

/* Ambient motion, used once. The hairline fills as the world approaches its next tick,
   which is the single most important fact about this product: nothing happens in
   between. Everything else on the page stays still. */

export default function TickBar({
  lastTickAt,
  intervalMinutes,
}: {
  lastTickAt: string | null;
  intervalMinutes: number;
}) {
  const [pct, setPct] = useState(0);

  useEffect(() => {
    if (!lastTickAt) return;
    const span = intervalMinutes * 60_000;
    const update = () => {
      const elapsed = Date.now() - new Date(lastTickAt).getTime();
      setPct(Math.min(100, (elapsed / span) * 100));
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [lastTickAt, intervalMinutes]);

  return (
    <div className="tickbar" role="presentation">
      <div className="tickbar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}
