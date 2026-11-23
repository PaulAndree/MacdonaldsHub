// Generates the artifacts derived from docs/api/openapi.yaml and checks they are up to date.
//   node scripts/contract.mjs generate   write src/api/schema.d.ts and src/example/contract.json
//   node scripts/contract.mjs check      fail when the committed files differ from the contract
// The JSON copy exists because the Docker build context is src/frontend and cannot see docs/.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
import { parse } from "yaml";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const contractPath = resolve(root, "../../docs/api/openapi.yaml");
const targets = {
  types: resolve(root, "src/api/schema.d.ts"),
  json: resolve(root, "src/example/contract.json"),
};

async function build() {
  const ast = await openapiTS(pathToFileURL(contractPath));
  const header =
    "// Generated from docs/api/openapi.yaml by scripts/contract.mjs. Do not edit by hand.\n";
  const spec = parse(readFileSync(contractPath, "utf-8"));
  return {
    types: header + astToString(ast),
    json: JSON.stringify(spec, null, 2) + "\n",
  };
}

const mode = process.argv[2];
const built = await build();

if (mode === "generate") {
  for (const key of Object.keys(targets)) writeFileSync(targets[key], built[key]);
  console.log("Generated:", Object.values(targets).map((p) => p.replace(root + "/", "")).join(", "));
} else if (mode === "check") {
  const stale = Object.keys(targets).filter((key) => {
    try {
      return readFileSync(targets[key], "utf-8") !== built[key];
    } catch {
      return true;
    }
  });
  if (stale.length > 0) {
    console.error(
      `Contract artifacts are out of date: ${stale.join(", ")}. Run "npm run contract:generate" and commit.`,
    );
    process.exit(1);
  }
  console.log("Contract artifacts are up to date.");
} else {
  console.error("Usage: node scripts/contract.mjs generate|check");
  process.exit(2);
}
