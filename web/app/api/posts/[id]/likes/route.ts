import { NextResponse } from "next/server";
import { getLikes } from "../../../../../lib/world";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const limit = Number(new URL(request.url).searchParams.get("limit") ?? 50);
  return NextResponse.json({ likers: await getLikes(id, limit) });
}
