// Ties the administrator's approval to an exact version of the API contract (ADR-16).
//   node scripts/approval.mjs hash    print the version and SHA-256 of the current contract
//   node scripts/approval.mjs check   fail when the contract differs from the approved one
// The approval record is docs/approvals/change_01_frontend.md and carries a line like:
//   <!-- approval: contractVersion=0.1.0 contractSha256=<64 hex characters> -->
// APPROVAL_FILE and CONTRACT_FILE override the record and contract locations (used by the tests).
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const contractPath = process.env.CONTRACT_FILE ?? resolve(root, "../../docs/api/openapi.yaml");
const approvalPath =
  process.env.APPROVAL_FILE ?? resolve(root, "../../docs/approvals/change_01_frontend.md");

const bytes = readFileSync(contractPath);
const sha = createHash("sha256").update(bytes).digest("hex");
const version = parse(bytes.toString("utf-8")).info.version;

const mode = process.argv[2];

if (mode === "hash") {
  console.log(`contractVersion=${version} contractSha256=${sha}`);
} else if (mode === "check") {
  const record = existsSync(approvalPath) ? readFileSync(approvalPath, "utf-8") : "";
  const match = record.match(/<!--\s*approval:\s*contractVersion=(\S+)\s+contractSha256=([0-9a-f]{64})\s*-->/);
  if (!match) {
    console.log("No contract approval is recorded yet; nothing to compare.");
  } else if (match[2] !== sha) {
    console.error(
      `The contract changed after its approval (approved version ${match[1]}, current ${version}). ` +
        "A new administrator approval is required: record it in docs/approvals/change_01_frontend.md " +
        '(use "npm run approval:hash" for the values).',
    );
    process.exit(1);
  } else {
    console.log(`The contract matches the approved version ${match[1]}.`);
  }
} else {
  console.error("Usage: node scripts/approval.mjs hash|check");
  process.exit(2);
}
