import { defineCloudflareConfig } from "@opennextjs/cloudflare";
import staticAssetsIncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/static-assets-incremental-cache";

// No incremental cache at all — the pages are rebuilt instead.
//
// ISR exists to refresh a page that changed at a moment you cannot predict. This world
// changes once an hour, on a schedule we own, so there is nothing to predict: the tick
// workflow rebuilds and redeploys the site right after it advances the world. Pages are
// plain static assets, which are unmetered and never written to at runtime.
//
// That removes the KV write ceiling, the R2 payment method, and the open question about
// whether middleware suppresses ISR on Workers — there is no ISR left to suppress. The cost
// is staleness bounded by one tick rather than half of one.
export default defineCloudflareConfig({
  incrementalCache: staticAssetsIncrementalCache,
  enableCacheInterception: true,
});
