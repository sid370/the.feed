import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// No incremental cache, deliberately. SSR routes work without one; only SSG/ISR needs a
// store, and the world is interactive now — a visitor who pokes has to see it immediately,
// which nothing that refreshes on a timer can promise.
//
// This also ends a detour. R2 wanted a payment method, KV allowed 1,000 writes a day, and
// baking the pages hourly traded away exactly the freshness an interactive world needs. All
// three were workarounds for a caching layer this shape does not want.
//
// If read volume ever justifies caching again, the cheap move is Cloudflare's edge cache via
// `s-maxage` on the response — free, unmetered, and no binding to configure. Reach for that
// before reaching for KV.
export default defineCloudflareConfig({});
