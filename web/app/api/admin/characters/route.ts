import { NextResponse } from "next/server";
import { denyAdmin } from "../../../../lib/admin";
import { query } from "../../../../lib/db";

const world = () => process.env.WORLD_ID ?? "main";

export async function GET(request: Request) {
  const denied = denyAdmin(request);
  if (denied) return denied;

  const rows = await query<any>("admin_characters", { world: world() });
  return NextResponse.json({
    characters: rows.map((r) => ({
      id: String(r.id),
      handle: r.handle,
      name: r.name,
      status: r.status,
      persona_card: r.persona_card,
      engagement_profile: r.engagement_profile,
    })),
  });
}
