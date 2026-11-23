import { describe, expect, it } from "vitest";
import { datasetOf, summaryOf } from "./dataset";
import { IncidentError, addFromBatch, checkManual, claim, correct, createManual, detailOf, filterIncidents, recordResult, seedIncidents } from "./incidents";

const store = () => seedIncidents();
const core = (over: Record<string, unknown> = {}) => ({
  provider: "uber eats" as const,
  orderId: "UE-200001",
  incidentDate: "2026-11-21",
  incidentTime: null,
  branch: "centro",
  claimAmount: "18.75",
  providerCosts: null,
  total: null,
  description: null,
  ...over,
});
const refused = (fn: () => unknown) => {
  try {
    fn();
  } catch (error) {
    return error as IncidentError;
  }
  throw new Error("expected a refusal");
};

describe("example incidents: listing", () => {
  it("starts with incidents in several states, some with absent values", () => {
    const all = filterIncidents(store(), {});
    expect(all.map((i) => i.id).sort()).toEqual(["inc-001", "inc-002", "inc-003", "inc-004", "inc-005", "inc-006"]);
    expect(all.some((i) => i.branch === null)).toBe(true);
    expect(all.some((i) => i.claimAmount === null)).toBe(true);
  });

  it("filters by provider, branch (including none), status and each kind of date", () => {
    const s = store();
    expect(filterIncidents(s, { provider: "glovo" }).map((i) => i.id).sort()).toEqual(["inc-003", "inc-005"]);
    expect(filterIncidents(s, { branch: "none" }).map((i) => i.id)).toEqual(["inc-002"]);
    expect(filterIncidents(s, { branch: "norte" }).map((i) => i.id).sort()).toEqual(["inc-003", "inc-005"]);
    expect(filterIncidents(s, { status: "send_error" }).map((i) => i.id)).toEqual(["inc-002"]);
    expect(filterIncidents(s, { dateKind: "claim", from: "2026-11-01", to: "2026-11-30" }).map((i) => i.id).sort()).toEqual(["inc-001", "inc-004", "inc-006"]);
    expect(filterIncidents(s, { dateKind: "recovery", from: "2026-11-01" }).map((i) => i.id).sort()).toEqual(["inc-004", "inc-005"]);
    // An incident with no claim date is outside any claim-date range, never assumed to be inside it.
    expect(filterIncidents(s, { dateKind: "claim", from: "2000-01-01" }).map((i) => i.id)).not.toContain("inc-002");
  });
});

describe("example incidents: checking a manual entry (RF-22)", () => {
  it("a key that does not exist is new", () => {
    expect(checkManual(store(), core()).outcome).toBe("new");
  });

  it("the same key and the same data is a duplicate", () => {
    const existing = filterIncidents(store(), {}).find((i) => i.id === "inc-001")!;
    const { id, batchId, status, channel, claimDate, recoveryDate, recoveredAmount, result, ...same } = existing;
    void [id, batchId, status, channel, claimDate, recoveryDate, recoveredAmount, result];
    expect(checkManual(store(), same).outcome).toBe("duplicate");
  });

  it("the same key with a different amount is a conflict that names the field", () => {
    const result = checkManual(store(), core({ orderId: "UE-098001", incidentDate: "2026-11-10", incidentTime: "19:40", claimAmount: "99.00" }));
    expect(result.outcome).toBe("conflict");
    expect(result.differingFields).toEqual(["claimAmount"]);
    expect(result.existing?.claimAmount).toBe("12.50");
  });

  it("a difference in only the time counts as a conflict", () => {
    const result = checkManual(store(), core({ orderId: "UE-098001", incidentDate: "2026-11-10", incidentTime: null, claimAmount: "12.50" }));
    expect(result.differingFields).toEqual(["incidentTime"]);
  });
});

describe("example incidents: manual entry", () => {
  it("creates an incident with no email and a first history entry", () => {
    const s = store();
    const created = createManual(s, core(), "admin-1");
    expect(created.status).toBe("imported_no_email");
    expect(created.channel).toBe("email");
    expect(created.batchId).toBeNull();
    expect(detailOf(s, created.id)?.history).toHaveLength(1);
  });

  it("refuses a key that exists and creates nothing", () => {
    const s = store();
    const before = s.items.length;
    const error = refused(() => createManual(s, core({ orderId: "UE-098001" }), "admin-1"));
    expect(error.status).toBe(409);
    expect(s.items).toHaveLength(before);
  });
});

describe("example incidents: claim, result and correction (UI-05, RF-21)", () => {
  it("claims an incident without email, recording the date in the history", () => {
    const s = store();
    const claimed = claim(s, "inc-003", "2026-11-21", "admin-1");
    expect(claimed.status).toBe("claimed");
    expect(claimed.claimDate).toBe("2026-11-21");
    const fields = detailOf(s, "inc-003")!.history.map((h) => h.field);
    expect(fields).toEqual(expect.arrayContaining(["status", "claimDate"]));
  });

  it("does not claim twice, nor an incident whose email is pending or failed", () => {
    const s = store();
    claim(s, "inc-003", "2026-11-21", "admin-1");
    expect(refused(() => claim(s, "inc-003", "2026-11-22", "admin-1")).code).toBe("claim_not_available");
    expect(refused(() => claim(s, "inc-002", "2026-11-22", "admin-1")).code).toBe("claim_not_available");
  });

  it("records a partial recovery explicitly and does not assume a full one", () => {
    const s = store();
    claim(s, "inc-003", "2026-11-21", "admin-1");
    const done = recordResult(s, "inc-003", { result: "resolved", recoveredAmount: "12.00", recoveryDate: "2026-11-25" }, "admin-1");
    expect(done.status).toBe("resolved");
    expect(done.recoveredAmount).toBe("12.00");
    expect(done.claimAmount).toBe("30.00");
  });

  it("can record a result with no amount: it stays absent, not zero", () => {
    const s = store();
    claim(s, "inc-003", "2026-11-21", "admin-1");
    expect(recordResult(s, "inc-003", { result: "rejected", recoveredAmount: null, recoveryDate: null }, "admin-1").recoveredAmount).toBeNull();
  });

  it("only records a result for a claimed incident", () => {
    expect(refused(() => recordResult(store(), "inc-003", { result: "resolved", recoveredAmount: null, recoveryDate: null }, "admin-1")).code).toBe("incident_not_claimed");
  });

  it("corrects a result, keeping each change with its reason, without touching the batch or emails", () => {
    const s = store();
    const before = detailOf(s, "inc-004")!.history.length;
    const corrected = correct(s, "inc-004", { result: "resolved", recoveredAmount: "20.00", recoveryDate: "2026-11-15", reason: "Se recuperó el importe completo." }, "admin-1");
    expect(corrected.recoveredAmount).toBe("20.00");
    expect(corrected.batchId).toBe("lote-0004");
    const added = detailOf(s, "inc-004")!.history.slice(before);
    expect(added).toHaveLength(1);
    expect(added[0]).toMatchObject({ kind: "correction", field: "recoveredAmount", previousValue: "12.00", newValue: "20.00", reason: "Se recuperó el importe completo." });
  });

  it("changing the result kind moves the status and is recorded", () => {
    const s = store();
    correct(s, "inc-004", { result: "rejected", recoveredAmount: null, recoveryDate: null, reason: "Rechazada por el proveedor." }, "admin-1");
    expect(detailOf(s, "inc-004")!.incident.status).toBe("rejected");
    const fields = detailOf(s, "inc-004")!.history.filter((h) => h.kind === "correction").map((h) => h.field);
    expect(fields).toEqual(expect.arrayContaining(["result", "recoveredAmount", "recoveryDate"]));
  });

  it("a correction with nothing changed adds no history", () => {
    const s = store();
    const before = detailOf(s, "inc-004")!.history.length;
    correct(s, "inc-004", { result: "resolved", recoveredAmount: "12.00", recoveryDate: "2026-11-15", reason: "Sin cambios." }, "admin-1");
    expect(detailOf(s, "inc-004")!.history).toHaveLength(before);
  });

  it("cannot correct an incident that has no result", () => {
    expect(refused(() => correct(store(), "inc-001", { result: "resolved", recoveredAmount: null, recoveryDate: null, reason: "x" }, "admin-1")).code).toBe("no_result_to_correct");
  });

  it("an unknown incident is a 404", () => {
    expect(refused(() => claim(store(), "inc-999", "2026-11-21", "admin-1")).status).toBe(404);
  });
});

describe("example incidents: confirming a batch creates them", () => {
  it("creates one per new row, with an email pending for Uber Eats and Just Eat and none for Glovo", () => {
    const s = store();
    addFromBatch(s, "lote-0007", "large");
    const created = s.items.filter((i) => i.batchId === "lote-0007");
    const summary = summaryOf("large");
    expect(created).toHaveLength(summary.incidentsToCreate);
    expect(created.filter((i) => i.status === "pending_send")).toHaveLength(summary.emailsToGenerate);
    expect(created.filter((i) => i.status === "imported_no_email")).toHaveLength(summary.withoutEmail);
    expect(created.every((i) => (i.provider === "glovo") === (i.channel === "glovo"))).toBe(true);
  });

  it("leaves out a row another batch confirmed meanwhile", () => {
    const s = store();
    const skip = datasetOf("large").rows.find((r) => r.class === "new" && r.fields.provider !== "glovo")!.rowNumber;
    addFromBatch(s, "lote-0007", "large", skip);
    expect(s.items.filter((i) => i.batchId === "lote-0007")).toHaveLength(summaryOf("large").incidentsToCreate - 1);
  });

  it("never creates an incident from an excluded row", () => {
    const s = store();
    addFromBatch(s, "lote-0007", "large");
    const keys = new Set(s.items.map((i) => `${i.provider}|${i.orderId}`));
    expect(keys.size).toBe(s.items.length);
  });
});
