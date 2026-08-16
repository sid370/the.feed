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
