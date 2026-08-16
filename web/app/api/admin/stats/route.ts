import { NextResponse } from "next/server";
import { denyAdmin } from "../../../../lib/admin";
import { query, queryOne } from "../../../../lib/db";

const WORLD = process.env.WORLD_ID ?? "main";
const num = (v: unknown): number => Number(v ?? 0);

export async function GET(request: Request) {
  const denied = denyAdmin(request);
  if (denied) return denied;

  const [totals, usage, recent] = await Promise.all([
    queryOne<any>("admin_totals", { world: WORLD }),
    queryOne<any>("admin_usage"),
    query<any>("admin_recent_ticks"),
  ]);

  const budget = num(process.env.TICK_BUDGET ?? 8);
  const interval = num(process.env.TICK_INTERVAL_MINUTES ?? 30);

  return NextResponse.json({
    posts: num(totals?.posts),
    likes: num(totals?.likes),
    active: num(totals?.active),
    open_batches: num(totals?.open_batches),
    blocked_headlines: num(totals?.blocked_headlines),
    usage: {
      input_tokens: num(usage?.input_tokens),
      output_tokens: num(usage?.output_tokens),
      cache_read_tokens: num(usage?.cache_read_tokens),
      cache_write_tokens: num(usage?.cache_write_tokens),
      failed_batches: num(usage?.failed_batches),
    },
    recent_ticks: recent.map((t) => ({
      id: num(t.id),
      turns_sent: num(t.turns_sent),
      posts_written: num(t.posts_written),
      news_share: t.news_share,
      started_at: t.started_at instanceof Date ? t.started_at.toISOString() : t.started_at,
      error: t.error,
    })),
    budget: {
      tick_budget: budget,
      interval_minutes: interval,
      turns_per_day: Math.round((1440 / interval) * budget),
    },
  });
}
