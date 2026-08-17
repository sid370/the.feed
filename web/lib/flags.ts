import "server-only";

// A function, not a const. On Workers, vars and secrets land on process.env while a request
// is being handled, so a module-scope read can run first and see nothing — which for a kill
// switch means it silently reads as "off" or "on" for reasons unrelated to configuration.
//
// Env values are also strings, and the string "false" is truthy: the other usual way a
// switch stops switching. Both hazards are handled once, here.
//
// Default off: the poke is the only write a visitor can perform, so it should require a
// deliberate opt-in rather than appear because a variable went missing.
export const pokeEnabled = (): boolean => process.env.POKE_ENABLED === "true";

// The gate is not a cost or abuse control — with the poke disabled the site is read-only, so
// there is nothing to spend or corrupt. What it contains is the real-person risk in PLAN.md
// §12: 46 public figures with real names, handles and photographs making fabricated
// first-person statements, and no per-post parody label since the chip was removed.
//
// Off by default now, deliberately. The site-wide `noindex` came off with it, so of the two
// controls §12 names — unlisted and gated — neither is left. What labels the world instead
// is the advisory in `layout.tsx` and the parody frame every title and preview carries; see
// lib/meta.ts. That frame is the substitute §12 asks for, on the surface that travels.
export const siteGateEnabled = (): boolean => process.env.SITE_GATE_ENABLED === "true";
