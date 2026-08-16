import "server-only";
import { NextResponse } from "next/server";
import { safeEqual } from "./session";

// On the deployed app this token unlocks SELECT and nothing else. The endpoints that spend
// money or rewrite persona cards — tick, draft, PATCH — stay on the local FastAPI service,
// so a leaked token buys someone a look at token counts. DEPLOY.md §3.
export function denyAdmin(request: Request): NextResponse | null {
  const token = process.env.ADMIN_TOKEN;
  if (!token) throw new Error("ADMIN_TOKEN is not set");
  if (safeEqual(request.headers.get("x-admin-token") ?? "", token)) return null;
  return NextResponse.json({ detail: "admin token required" }, { status: 403 });
}
