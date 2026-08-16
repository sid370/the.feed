import { defineCloudflareConfig } from "@opennextjs/cloudflare";
import r2IncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/r2-incremental-cache";

// Without an incrementalCache override, SSG/ISR does not work on Workers at all — SSR routes
// still serve, but every request re-renders. That would quietly undo the entire cost model
// in DEPLOY.md §3, so this is load-bearing rather than an optimisation.
//
// R2 over KV: revalidating 161 prerendered pages hourly is ~3,900 writes/day, and KV's free
// tier allows 1,000/day. R2 allows a million a month and we need about 116,000.
export default defineCloudflareConfig({
  incrementalCache: r2IncrementalCache,
});
