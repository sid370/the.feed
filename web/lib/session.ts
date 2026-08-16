// The session cookie, reimplemented for Web Crypto so middleware can check it at the edge.
//
// This must stay byte-identical to _session_value() in charsocial/api/main.py — same key,
// same message, same 32-char truncation. Disagree and every existing cookie stops validating
// with no error anywhere. scripts/check_session_parity.mjs asserts the two agree.
//
// Worth being clear about what this is: a static HMAC of a shared password, identical for
// every visitor and never expiring. It is containment, not authentication. See DEPLOY.md §4.
export const SESSION_COOKIE = "cs_session";

export async function sessionValue(password: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(password),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode("charsocial"));
  return [...new Uint8Array(mac)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

export function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
