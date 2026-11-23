// Checks which build variant a dist folder is (design D1, D10).
//   node scripts/check-bundle.mjs standard [dist]   fails if ANY example marker is present
//   node scripts/check-bundle.mjs example  [dist]   fails if the example layer is missing
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const variant = process.argv[2];
const dist = resolve(root, process.argv[3] ?? "dist");

/** Strings that exist only in the example layer. */
const markers = [
  "dh-example-scenario",
  "example.invalid",
  "Error interno de ejemplo",
  "nada de lo que ve es real",
  "Escenario de ejemplo",
];
const workerFile = "mockServiceWorker.js";

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? files(full) : [full];
  });
}

if (!["standard", "example"].includes(variant) || !existsSync(dist)) {
  console.error("Usage: node scripts/check-bundle.mjs standard|example [dist]  (the dist folder must exist)");
  process.exit(2);
}

const all = files(dist);
const hasWorker = all.some((f) => f.endsWith(workerFile));
const found = new Set();
for (const file of all) {
  if (/\.(js|html|css|json|map)$/.test(file)) {
    const text = readFileSync(file, "utf-8");
    for (const marker of markers) if (text.includes(marker)) found.add(marker);
  }
}

const problems = [];
if (variant === "standard") {
  if (hasWorker) problems.push(`${workerFile} is in the standard build`);
  for (const marker of found) problems.push(`example marker "${marker}" is in the standard build`);
} else {
  if (!hasWorker) problems.push(`${workerFile} is missing from the example build`);
  for (const marker of markers) {
    if (!found.has(marker)) problems.push(`example marker "${marker}" is missing from the example build`);
  }
}

if (problems.length > 0) {
  console.error(`The ${variant} build is wrong:\n- ${problems.join("\n- ")}`);
  process.exit(1);
}
console.log(`The ${variant} build is as expected (${all.length} files checked).`);
