// Compiles db/queries/*.sql into web/lib/queries.gen.ts.
//
// Workers have no filesystem at runtime, so the SQL cannot be read at request time the way
// charsocial/queries.py reads it. Generating a module keeps the .sql files the single source
// and leaves the deployed bundle self-contained. Parsing mirrors charsocial/queries.py; the
// npm `check:queries` script fails if the checked-in output has drifted from the .sql files.
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const queryDir = join(root, "db", "queries");
const out = join(root, "web", "lib", "queries.gen.ts");

const NAME = /^--\s*name:\s*(\w+)\s*$/gm;
// A ::float cast is not a placeholder. The lookbehind is what keeps it one.
const PARAM = /(?<!:):([a-z_][a-z0-9_]*)/g;

function stripBody(body) {
  const lines = body.trim().split("\n");
  while (lines.length && lines[lines.length - 1].trimStart().startsWith("--")) lines.pop();
  return lines.join("\n").trim();
}

const queries = new Map();
for (const file of readdirSync(queryDir).filter((f) => f.endsWith(".sql")).sort()) {
  const chunks = readFileSync(join(queryDir, file), "utf8").split(NAME);
  for (let i = 1; i < chunks.length; i += 2) {
    const name = chunks[i];
    if (queries.has(name)) throw new Error(`duplicate query name '${name}' in ${file}`);

    // Positional $n, numbered by first appearance so a repeated :world reuses one slot.
    const params = [];
    const text = stripBody(chunks[i + 1]).replace(PARAM, (_, p) => {
      if (!params.includes(p)) params.push(p);
      return `$${params.indexOf(p) + 1}`;
    });
    queries.set(name, { text, params });
  }
}
if (!queries.size) throw new Error(`no queries found in ${queryDir}`);

const names = [...queries.keys()];
const generated =
  `// Generated from db/queries/*.sql by scripts/gen_queries.mjs. Do not edit.\n` +
    `export type QueryName =\n${names.map((n) => `  | "${n}"`).join("\n")};\n\n` +
    `export const SQL: Record<QueryName, { text: string; params: string[] }> = {\n` +
    names
      .map((n) => {
        const { text, params } = queries.get(n);
        return `  ${n}: { text: ${JSON.stringify(text)}, params: ${JSON.stringify(params)} },`;
      })
      .join("\n") +
  `\n};\n`;

if (process.argv.includes("--check")) {
  if (readFileSync(out, "utf8") !== generated) {
    console.error(`${out} is stale. Run: node scripts/gen_queries.mjs`);
    process.exit(1);
  }
  console.log(`queries.gen.ts is current (${names.length} queries)`);
} else {
  writeFileSync(out, generated);
  console.log(`wrote ${out} (${names.length} queries)`);
}
