// Fails the deploy if local env values were baked into the Worker bundle.
//
// OpenNext writes whatever Next loaded into .open-next/cloudflare/next-env.mjs, split by
// environment. `.env.local` is loaded in *every* environment including a production build,
// so a deploy run with that file present shipped the documented dev password to a public URL
// — it happened once, and nothing in the build output said so.
//
// Dev values must live in .env.development.local, which only `next dev` loads. Then the
// `production` map here stays empty and real values come from `wrangler secret put`.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const file = join(dirname(fileURLToPath(import.meta.url)), "..", "web", ".open-next", "cloudflare", "next-env.mjs");

let source;
try {
  source = readFileSync(file, "utf8");
} catch {
  console.error(`cannot read ${file} — run the OpenNext build first`);
  process.exit(1);
}

const match = source.match(/export const production = (\{.*?\});/s);
if (!match) {
  console.error("could not find the production env map; the adapter's output format changed");
  process.exit(1);
}

const baked = Object.keys(JSON.parse(match[1]));
if (baked.length) {
  console.error(
    `refusing to deploy: ${baked.length} value(s) baked into the bundle — ${baked.join(", ")}.\n` +
      "Move them out of web/.env.local (loaded in every environment) into\n" +
      "web/.env.development.local (loaded only by `next dev`), and set the real ones with\n" +
      "`npx wrangler secret put <NAME>`.",
  );
  process.exit(1);
}
console.log("no env values baked into the bundle");
