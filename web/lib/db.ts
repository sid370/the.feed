import { neon } from "@neondatabase/serverless";
import { SQL, type QueryName } from "./queries.gen";

// Neon's driver speaks HTTP, which is the only thing a Worker can open; local postgres
// needs a real socket. One line of detection keeps `make web` working against the docker
// database, which is where this project's bugs actually get found.
const url = process.env.DATABASE_URL ?? "";
const overHttp = url.includes("neon.tech");

// node-postgres is imported lazily and only on the local branch. A static import would pull
// node:net and node:tls into the Worker bundle for code that can never run there.
let pool: { query(text: string, values: unknown[]): Promise<{ rows: unknown[] }> } | undefined;

export async function query<T>(
  name: QueryName,
  args: Record<string, unknown> = {},
): Promise<T[]> {
  if (!url) throw new Error("DATABASE_URL is not set");
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
