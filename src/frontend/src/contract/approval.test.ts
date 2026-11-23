import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const script = resolve(process.cwd(), "scripts/approval.mjs");

function run(approvalFile: string) {
  return spawnSync(process.execPath, [script, "check"], {
    env: { ...process.env, APPROVAL_FILE: approvalFile },
    encoding: "utf-8",
  });
}

/** Writes an approval record carrying the given contract values. */
function record(dir: string, version: string, sha: string): string {
  const file = join(dir, "approval.md");
  writeFileSync(
    file,
    `# Approval\n\n<!-- approval: contractVersion=${version} contractSha256=${sha} -->\n`,
  );
  return file;
}

function currentValues() {
  const out = execFileSync(process.execPath, [script, "hash"], { encoding: "utf-8" }).trim();
  const [, version, sha] = out.match(/contractVersion=(\S+) contractSha256=([0-9a-f]{64})/) ?? [];
  return { version, sha };
}

describe("contract approval check (ADR-16)", () => {
  it("passes with a notice when no approval is recorded yet", () => {
    const dir = mkdtempSync(join(tmpdir(), "approval-"));
    const result = run(join(dir, "missing.md"));
    expect(result.status).toBe(0);
    expect(result.stdout).toContain("No contract approval is recorded yet");
  });

  it("passes when the record matches the current contract", () => {
    const dir = mkdtempSync(join(tmpdir(), "approval-"));
    const { version, sha } = currentValues();
    const result = run(record(dir, version, sha));
    expect(result.status).toBe(0);
    expect(result.stdout).toContain(`approved version ${version}`);
  });

  it("fails and asks for a new approval when the contract changed after it", () => {
    const dir = mkdtempSync(join(tmpdir(), "approval-"));
    const { version, sha } = currentValues();
    const altered = sha.replace(/^./, sha[0] === "0" ? "1" : "0");
    const result = run(record(dir, version, altered));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("new administrator approval is required");
  });

  it("detects a real edit of the contract file", () => {
    const dir = mkdtempSync(join(tmpdir(), "approval-"));
    const { version, sha } = currentValues();
    const approved = record(dir, version, sha);
    const contract = readFileSync(resolve(process.cwd(), "../../docs/api/openapi.yaml"), "utf-8");
    const unchanged = join(dir, "unchanged.yaml");
    const edited = join(dir, "edited.yaml");
    writeFileSync(unchanged, contract);
    writeFileSync(edited, contract.replace(`version: ${version}`, "version: 9.9.9"));
    const check = (file: string) =>
      spawnSync(process.execPath, [script, "check"], {
        env: { ...process.env, APPROVAL_FILE: approved, CONTRACT_FILE: file },
        encoding: "utf-8",
      });
    expect(check(unchanged).status).toBe(0);
    const result = check(edited);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(`approved version ${version}, current 9.9.9`);
  });
});
