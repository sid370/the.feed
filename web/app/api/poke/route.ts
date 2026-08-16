import { NextResponse } from "next/server";
import { queryOne } from "../../../lib/db";
import { POKE_ENABLED } from "../../../lib/flags";

// A human reply. It enters the world as a post plus a notification — it does NOT trigger a
// generation. The character answers on the next tick, out of the same budget as everyone
// else, which is what keeps this path from being a way to spend without limit.

const WORLD = process.env.WORLD_ID ?? "main";
const DAILY_CAP = Number(process.env.POKE_DAILY_CAP ?? 100);

export async function POST(request: Request) {
  // 404 rather than 403: a disabled feature should look absent, not merely locked. Checked
  // before the body is read, so a flood of pokes costs nothing at all while this is off.
  if (!POKE_ENABLED) return new NextResponse("Not Found", { status: 404 });

  const body = (await request.json()) as {
    post_id?: string;
    body?: string;
    display_name?: string;
  };

  // Both fields interpolate into a character's next prompt under markdown headings that are
  // structurally identical to the WORLD_RULES sections, and any poison persists via
  // memory_notes. Collapsing newlines removes the ability to forge a heading.
  const clean = (body.body ?? "").split(/\s+/).filter(Boolean).join(" ").slice(0, 280);
  const author =
    (body.display_name ?? "").toLowerCase().replace(/[^a-z0-9_]/g, "").slice(0, 24) || "guest";
  if (!clean) return NextResponse.json({ detail: "empty" }, { status: 400 });
  if (!body.post_id) return NextResponse.json({ detail: "no such post" }, { status: 404 });

  const today = await queryOne<{ n: string }>("human_posts_today");
  if (Number(today?.n ?? 0) >= DAILY_CAP) {
    return NextResponse.json({ detail: "daily poke limit reached" }, { status: 429 });
  }

  const target = await queryOne<{ character_id: string | null; root: string }>("poke_target", {
    post: body.post_id,
  });
  if (!target) return NextResponse.json({ detail: "no such post" }, { status: 404 });

  const created = await queryOne<{ id: string }>("insert_human_poke", {
    world: WORLD,
    author,
    body: clean,
    parent: body.post_id,
    root: target.root,
    character: target.character_id,
  });

  return NextResponse.json({ ok: true, id: String(created!.id) });
}
