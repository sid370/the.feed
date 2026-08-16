import { defineCloudflareConfig } from "@opennextjs/cloudflare";
import kvIncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/kv-incremental-cache";

// Without an incrementalCache override, SSG/ISR does not work on Workers at all — SSR routes
// still serve, but every request re-renders. That would quietly undo the entire cost model
// in DEPLOY.md §3, so this is load-bearing rather than an optimisation.
//
// KV rather than R2, which is what the OpenNext docs recommend: R2 cannot be enabled without
// a payment method on the account, and KV is included in the Workers free plan. The docs warn
// KV is eventually consistent — irrelevant here, where the world only changes once an hour
// and pages are deliberately served up to half an hour stale.
//
// The free tier allows 1,000 writes a day. A write happens only when a stale page is actually
// requested, so the rate follows traffic rather than the 161 prerendered pages. If it is ever
// exceeded, KV rejects the write and the page serves stale — degraded, not down, which is the
// same fail-closed property every other tier in this stack has.
export default defineCloudflareConfig({
  incrementalCache: kvIncrementalCache,
});
