import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse } from "yaml";

/** Location of the versioned contract, relative to this package (tests run from src/frontend). */
export const CONTRACT_PATH = resolve(process.cwd(), "../../docs/api/openapi.yaml");

export type Json = Record<string, unknown>;

export function loadContract(): Json {
  return parse(readFileSync(CONTRACT_PATH, "utf-8")) as Json;
}
