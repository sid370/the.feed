// Asserts web/lib/session.ts and charsocial/api/main.py derive the same cookie value.
//
// A mismatch is silent: middleware would simply reject every cookie the API issued, with no
// error to trace. Cheap to check, so check it.
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const { sessionValue } = await import(join(root, "web/lib/session.ts"));

const python = join(root, ".venv/bin/python");
let failed = false;

for (const password of ["letmein", "hunter2", "a", "ünïcödé pass", "x".repeat(200)]) {
  const expected = execFileSync(
    python,
    ["-c", 'import hmac,sys;print(hmac.new(sys.argv[1].encode(),b"charsocial","sha256").hexdigest()[:32])', password],
    { encoding: "utf8" },
  ).trim();
  const actual = await sessionValue(password);
  const ok = actual === expected;
  failed ||= !ok;
  console.log(`${ok ? "ok  " : "FAIL"}  ${JSON.stringify(password.slice(0, 20))} → ${actual}`);
  if (!ok) console.log(`      python gave ${expected}`);
}

process.exit(failed ? 1 : 0);
