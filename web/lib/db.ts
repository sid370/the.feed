import { neon } from "@neondatabase/serverless";
import { SQL, type QueryName } from "./queries.gen";

// Read per call, never at module scope. On Workers, bindings and secrets are populated onto
// process.env as part of handling a request, so a top-level read can run first and capture
// an empty string — which would surface as "DATABASE_URL is not set" on a Worker where the
// secret is definitely set.
const databaseUrl = () => process.env.DATABASE_URL ?? "";

// node-postgres is imported lazily and only on the local branch. A static import would pull
// node:net and node:tls into the Worker bundle for code that can never run there.
let pool: { query(text: string, values: unknown[]): Promise<{ rows: unknown[] }> } | undefined;

export async function query<T>(
  name: QueryName,
  args: Record<string, unknown> = {},
): Promise<T[]> {
  const url = databaseUrl();
  if (!url) throw new Error("DATABASE_URL is not set");
  // Neon's driver speaks HTTP, the only thing a Worker can open; local postgres needs a real
  // socket. This is what keeps `make web` working against the docker database.
  const overHttp = url.includes("neon.tech");
  const { text, params } = SQL[name];
  const values = params.map((p) => {
    if (!(p in args)) throw new Error(`query '${name}' is missing parameter '${p}'`);
    return args[p];
  });

  if (overHttp) return (await neon(url).query(text, values)) as T[];

  if (!pool) {
    const { Pool } = await import("pg");
    pool = new Pool({ connectionString: url });
  }
  return (await pool.query(text, values)).rows as T[];
}

export async function queryOne<T>(
  name: QueryName,
  args: Record<string, unknown> = {},
): Promise<T | null> {
  return (await query<T>(name, args))[0] ?? null;
}
