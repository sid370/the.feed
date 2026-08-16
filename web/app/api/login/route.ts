import { NextResponse } from "next/server";
import { SESSION_COOKIE, safeEqual, sessionValue } from "../../../lib/session";

export async function POST(request: Request) {
  const password = process.env.SITE_PASSWORD;
  if (!password) throw new Error("SITE_PASSWORD is not set");

  const { password: given } = (await request.json()) as { password?: string };
  if (!given || !safeEqual(given, password)) {
    return NextResponse.json({ detail: "wrong password" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  // "lax" now that the app and its API are one origin. It was "none" only because a
  // tunnelled API sat on a different site in development, which gave up the browser's
  // cross-site CSRF protection on /api/poke for nothing we still need.
  response.cookies.set(SESSION_COOKIE, await sessionValue(password), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 30,
    path: "/",
  });
  return response;
}
