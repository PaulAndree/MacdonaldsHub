import { describe, expect, it } from "vitest";
import { createManual, claim, seedIncidents } from "./incidents";
import { type MetricsQuery, computeMetrics } from "./metrics";

const base: MetricsQuery = { dateKind: "claim", from: null, to: null, provider: null, branch: null };
const run = (over: Partial<MetricsQuery> = {}, store = seedIncidents()) => computeMetrics(store, { ...base, ...over }, "test");
const channel = (m: ReturnType<typeof run>, name: "email" | "glovo") => m.channels.find((c) => c.channel === name)!;

describe("example dashboard figures (RF-15)", () => {
  it("keeps email and Glovo as separate figures, always both", () => {
    const m = run();
    expect(m.channels.map((c) => c.channel)).toEqual(["email", "glovo"]);
    expect(channel(m, "email")).toMatchObject({ claimedCount: 3, claimedAmount: "32.50", recoveredCount: 1, recoveredAmount: "12.00" });
    expect(channel(m, "glovo")).toMatchObject({ claimedCount: 1, claimedAmount: "10.00", recoveredCount: 1, recoveredAmount: "8.00" });
  });

  it("sums exactly and leaves out an absent amount instead of counting it as zero", () => {
    const email = channel(run(), "email");
    expect(email.claimedAmount).toBe("32.50"); // 12.50 + 20.00; the incident with no amount adds nothing
    expect(email.incompleteCount).toBe(1);
    expect(run().warnings.map((w) => w.code)).toContain("incomplete_amounts");
  });

  it("flags how many incidents the total is missing an amount for", () => {
    const warning = run().warnings.find((w) => w.code === "incomplete_amounts")!;
    expect(warning.count).toBe(1);
    expect(warning.message).toContain("1 incidencia sin importe");
  });

  it("the rate is an example criterion and is only given when it can be worked out", () => {
    const m = run();
    expect(channel(m, "email").recoveryRate).toBe("0.3692");
    expect(channel(m, "glovo").recoveryRate).toBe("0.8000");
    expect(m.criteria).toEqual({ status: "example", pendingDecision: "P-04" });
    const empty = run({ provider: "glovo", from: "2030-01-01" });
    expect(channel(empty, "glovo").recoveryRate).toBeNull();
  });

  it("an empty channel has no amounts, which is not zero", () => {
    const m = run({ provider: "glovo", from: "2030-01-01" });
    expect(channel(m, "glovo")).toMatchObject({ claimedCount: 0, claimedAmount: null, recoveredAmount: null, incompleteCount: 0 });
    expect(m.warnings.map((w) => w.code)).toContain("no_data");
  });

  it("breaks the figures down by provider and branch, with a missing branch as null", () => {
    const store = seedIncidents();
    createManual(store, { provider: "glovo", orderId: "GL-9", incidentDate: "2026-11-21", incidentTime: null, branch: null, claimAmount: "5.00", providerCosts: null, total: null, description: null }, "admin-1");
    claim(store, store.items.at(-1)!.id, "2026-11-21", "admin-1");
    const rows = run({}, store).breakdown;
    expect(rows.map((r) => `${r.provider}/${r.branch}`).sort()).toEqual(["glovo/norte", "glovo/null", "just eat/centro", "uber eats/centro"]);
    expect(rows.find((r) => r.provider === "just eat")).toMatchObject({ claimedAmount: null, incompleteCount: 1 });
  });

  it("changing the date criterion changes what is counted", () => {
    // Recovered between 1 and 30 November: only what was recovered then, and that was claimed.
    const byRecovery = run({ dateKind: "recovery", from: "2026-11-01", to: "2026-11-30" });
    expect(channel(byRecovery, "email").claimedCount).toBe(1);
    expect(channel(byRecovery, "glovo").claimedCount).toBe(1);
    // Claimed in November: Glovo's claim was in October.
    const byClaim = run({ dateKind: "claim", from: "2026-11-01", to: "2026-11-30" });
    expect(channel(byClaim, "glovo").claimedCount).toBe(0);
    expect(channel(byClaim, "email").claimedCount).toBe(3);
    // By the date of the incident: only those that happened from 12 November.
    const byIncident = run({ dateKind: "incident", from: "2026-11-12" });
    expect(channel(byIncident, "email").claimedCount).toBe(1); // inc-001 happened on 10 November
    expect(byIncident.dateKind).toBe("incident");
  });

  it("filters by provider and by branch", () => {
    expect(channel(run({ provider: "uber eats" }), "email").claimedCount).toBe(2);
    expect(channel(run({ branch: "norte" }), "glovo").claimedCount).toBe(1);
    expect(channel(run({ branch: "none" }), "email").claimedCount).toBe(0);
  });

  it("lists the claims still without a result, oldest first, with their age in days", () => {
    const pending = run().pendingClaims;
    expect(pending).toEqual([
      { incidentId: "inc-006", provider: "just eat", claimDate: "2026-11-19", ageDays: 3 },
      { incidentId: "inc-001", provider: "uber eats", claimDate: "2026-11-20", ageDays: 2 },
    ]);
  });

  it("carries the environment the figures belong to", () => {
    expect(computeMetrics(seedIncidents(), base, "production").environment).toBe("production");
    expect(run().environment).toBe("test");
  });
});
