import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, safeEqual, sessionValue } from "./lib/session";

// Two controls, and the order between them is the point.
//
// The gate runs here rather than inside a page because pages are cached: a cookie check
// inside a cached render is evaluated once and then served to everyone. Middleware runs
// before the cache lookup, costs no query, and lets one cached render serve every visitor.
//
// The rate limiter runs before the handler for the same reason it exists at all — a poke
// rejected by POKE_DAILY_CAP still costs a SELECT, so refusing it here is what keeps a
// flood off Neon. See DEPLOY.md §4.

const PUBLIC = ["/login", "/api/login"];

// Admin carries its own credential in a header; the shared password says nothing about it.
const ADMIN = "/api/admin";

type Limiter = { limit(o: { key: string }): Promise<{ success: boolean }> };

async function limited(request: NextRequest, binding: string): Promise<boolean> {
  let env: Record<string, Limiter | undefined>;
  try {
    const { getCloudflareContext } = await import("@opennextjs/cloudflare");
    env = getCloudflareContext().env as unknown as Record<string, Limiter | undefined>;
  } catch {
    return false; // Not on Workers — `next dev` has no bindings and must still run.
  }
  const limiter = env?.[binding];
  if (!limiter) return false;
  const ip = request.headers.get("cf-connecting-ip") ?? "anon";
  return !(await limiter.limit({ key: `${binding}:${ip}` })).success;
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const bucket = pathname === "/api/poke" ? "POKES" : "READS";
  if (await limited(request, bucket)) {
    return new NextResponse("slow down", { status: 429 });
  }

  if (PUBLIC.includes(pathname) || pathname.startsWith(ADMIN)) return NextResponse.next();

  const password = process.env.SITE_PASSWORD;
  if (!password) throw new Error("SITE_PASSWORD is not set");
  if (safeEqual(request.cookies.get(SESSION_COOKIE)?.value ?? "", await sessionValue(password))) {
    return NextResponse.next();
  }

  // An API call cannot follow a redirect usefully; the client turns 401 into a route change.
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "password required" }, { status: 401 });
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|avatars|favicon.ico|robots.txt).*)"],
};
