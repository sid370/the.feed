import "server-only";

// Env values are strings, and the string "false" is truthy — the single most likely way a
// kill switch silently fails to kill anything. Parsed once, here, rather than at each site.
//
// Default off: the poke is the only write a visitor can perform, so it should require a
// deliberate opt-in rather than appear because a variable went missing.
export const POKE_ENABLED = process.env.POKE_ENABLED === "true";
