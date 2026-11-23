/* eslint-disable @typescript-eslint/no-explicit-any -- responses are inspected loosely in these tests */
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { type Operation, example, operations } from "./contract";
import { handlers } from "./handlers";
import { requiredPermission } from "./permissions";
import { resetScenario, setScenario } from "./scenario";
import { resetStore } from "./state";

const server = setupServer(...handlers);
const url = (path: string) => `${location.origin}${path}`;

async function call(method: string, path: string, body?: unknown) {
  const response = await fetch(url(path), {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const type = response.headers.get("content-type") ?? "";
  const data = type.includes("json") ? ((await response.json()) as Record<string, any>) : null;
  return { status: response.status, data, response };
}

const fill = (op: Operation) =>
  op.path
    .replace("{batchId}", "lote-0005")
    .replace("{incidentId}", "inc-001")
    .replace("{authorizationId}", "auth-1")
    .replace("{branchId}", "br-1")
    .replace("{providerId}", "pr-1");

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("example layer covers the whole contract", () => {
  it("knows every operation of the contract and its required permission", () => {
    expect(operations.length).toBe(24);
    for (const op of operations) expect(requiredPermission).toHaveProperty(op.id);
  });

  it.each(operations.map((op) => [op.id, op] as const))("%s answers with a documented status", async (_id, op) => {
    const body = ["post", "put"].includes(op.method)
      ? op.id === "createBatch"
        ? { fileName: "a.xlsx", sizeBytes: 1 }
        : op.id === "confirmBatch"
          ? { reviewedVersion: "0".repeat(64) }
          : {}
      : undefined;
    const { status } = await call(op.method.toUpperCase(), fill(op), body);
    expect(op.statuses).toContain(status);
  });

  it("serves a downloadable file for the download operations", async () => {
    const { status, response } = await call("GET", "/api/batches/lote-0005/excluded-report");
    expect(status).toBe(200);
    expect(response.headers.get("content-type")).toContain("spreadsheetml");
    expect((await response.arrayBuffer()).byteLength).toBeGreaterThan(500);
  });

  it("has no operation for the screens this application does not have", () => {
    const ids = operations.map((op) => op.id);
    for (const gone of ["listAuthorizations", "listBranches", "listProviders", "listAudit", "downloadConfirmedOriginal"]) {
      expect(ids).not.toContain(gone);
    }
  });
});

describe("roles", () => {
  it("the global manager role is denied operations that change things with a 403", async () => {
    setScenario({ role: "global_manager" });
    for (const [method, path] of [
      ["GET", "/api/email-queue"],
      ["POST", "/api/email-queue/pause"],
      ["POST", "/api/batches"],
      ["POST", "/api/incidents/manual"],
    ] as const) {
      const { status, data } = await call(method, path, method === "POST" ? {} : undefined);
      expect(status, `${method} ${path}`).toBe(403);
      expect(data?.code).toBe("not_authorized");
    }
  });

  it("the global manager role can still consult incidents, the dashboard and its session", async () => {
    setScenario({ role: "global_manager" });
    expect((await call("GET", "/api/incidents")).status).toBe(200);
    expect((await call("GET", "/api/metrics")).status).toBe(200);
    expect((await call("GET", "/api/session")).data?.role).toBe("global_manager");
  });
});

describe("batch flow keeps its own state", () => {
  const create = (fileName = "incidencias.xlsx") =>
    call("POST", "/api/batches", { fileName, sizeBytes: 1000 });

  async function prepared(fileName?: string) {
    const created = await create(fileName);
    const id = created.data?.batch.id as string;
    await call("POST", `/api/batches/${id}/uploaded`);
    const batch = await call("GET", `/api/batches/${id}`);
    return { id, created, batch: batch.data as Record<string, any> };
  }

  it("creates a batch with a temporary upload address, then prepares it for review", async () => {
    const { created, batch } = await prepared();
    expect(created.status).toBe(201);
    expect(created.data?.upload.method).toBe("PUT");
    expect(batch.state).toBe("in_review");
    // The summary comes from the same rows the preview lists.
    const rows = await call("GET", `/api/batches/${created.data?.batch.id}/rows`);
    expect(batch.summary.totals).toEqual(rows.data?.totalsByClass);
    expect(Object.values(batch.summary.totals).reduce((a: number, b) => a + (b as number), 0)).toBe(500);
  });

  it("accepts the upload to the temporary address and rejects it when storage fails", async () => {
    const ok = await fetch("https://example.invalid/uploads/lote-9?sp=c", { method: "PUT", body: "x" });
    expect(ok.status).toBe(201);
    setScenario({ failure: "storage" });
    const bad = await fetch("https://example.invalid/uploads/lote-9?sp=c", { method: "PUT", body: "x" });
    expect(bad.status).toBe(403);
  });

  it("allows one unconfirmed batch per user and names the pending one", async () => {
    const first = await create();
    const second = await create();
    expect(second.status).toBe(409);
    expect(second.data?.code).toBe("unconfirmed_batch_exists");
    expect(second.data?.details.batchId).toBe(first.data?.batch.id);
  });

  it("a rejected batch does not block a new upload", async () => {
    const { batch } = await prepared("sin-order-id.xlsx");
    expect(batch.state).toBe("rejected");
    expect(batch.rejection.reason).toBe("missing_required_header");
    expect((await create()).status).toBe(201);
  });

  it("recognizes the other rejection and the identical-file notice by file name", async () => {
    expect((await prepared("dos-hojas.xlsx")).batch.rejection.reason).toBe("multiple_worksheets");
    resetStore();
    const identical = (await prepared("identica.xlsx")).batch;
    expect(identical.state).toBe("in_review");
    expect(identical.identicalFile).not.toBeNull();
  });

  it("confirms once and returns the stored result when repeated", async () => {
    const { id, batch } = await prepared();
    const first = await call("POST", `/api/batches/${id}/confirm`, { reviewedVersion: batch.reviewedVersion });
    expect(first.status).toBe(200);
    expect(first.data?.alreadyConfirmed).toBe(false);
    const again = await call("POST", `/api/batches/${id}/confirm`, { reviewedVersion: batch.reviewedVersion });
    expect(again.status).toBe(200);
    expect(again.data?.alreadyConfirmed).toBe(true);
    expect(again.data?.createdIncidents).toBe(first.data?.createdIncidents);
    expect((await call("GET", `/api/batches/${id}`)).data?.state).toBe("confirmed");
  });

  it("refuses to confirm a different file version", async () => {
    const { id } = await prepared();
    const result = await call("POST", `/api/batches/${id}/confirm`, { reviewedVersion: "f".repeat(64) });
    expect(result.status).toBe(422);
  });

  it("reports rows that matched at confirmation when the scenario asks for it", async () => {
    setScenario({ matchesAtConfirmation: true });
    const { id, batch } = await prepared();
    const result = await call("POST", `/api/batches/${id}/confirm`, { reviewedVersion: batch.reviewedVersion });
    expect(result.data?.excludedAtConfirmation).toHaveLength(1);
  });

  it("a discarded batch cannot be confirmed, and a confirmed one cannot be discarded", async () => {
    const { id, batch } = await prepared();
    expect((await call("POST", `/api/batches/${id}/discard`)).data?.state).toBe("discarded");
    const refused = await call("POST", `/api/batches/${id}/confirm`, { reviewedVersion: batch.reviewedVersion });
    expect(refused.status).toBe(409);
    expect(refused.data?.code).toBe("batch_discarded");

    const other = await prepared();
    await call("POST", `/api/batches/${other.id}/confirm`, { reviewedVersion: other.batch.reviewedVersion });
    const cannot = await call("POST", `/api/batches/${other.id}/discard`);
    expect(cannot.status).toBe(409);
    expect(cannot.data?.code).toBe("batch_already_confirmed");
  });

  it("Cerrar sesión discards every unconfirmed batch and reports none when there are none", async () => {
    setScenario({ pendingBatch: true });
    expect((await call("GET", "/api/batches/pending")).status).toBe(200);
    const discarded = await call("POST", "/api/batches/discard-unconfirmed");
    expect(discarded.data).toEqual({ discarded: 1, batchIds: ["lote-0006"] });
    expect((await call("GET", "/api/batches/pending")).status).toBe(204);
    expect((await call("POST", "/api/batches/discard-unconfirmed")).data?.discarded).toBe(0);
  });

  it("starts with no pending batch unless the scenario says so", async () => {
    expect((await call("GET", "/api/batches/pending")).status).toBe(204);
  });
});

describe("queue and failures", () => {
  it("pausing persists across reads and resuming undoes it", async () => {
    expect((await call("GET", "/api/email-queue")).data?.status.paused).toBe(false);
    await call("POST", "/api/email-queue/pause");
    expect((await call("GET", "/api/email-queue")).data?.status.paused).toBe(true);
    await call("POST", "/api/email-queue/resume");
    expect((await call("GET", "/api/email-queue")).data?.status.paused).toBe(false);
  });

  it("returns the empty examples when the scenario has no data", async () => {
    setScenario({ emptyData: true });
    expect((await call("GET", "/api/incidents")).data?.total).toBe(0);
    expect((await call("GET", "/api/metrics")).data?.channels).toEqual([]);
  });

  it("simulates a server error and a network failure, but never for the session", async () => {
    setScenario({ failure: "server" });
    expect((await call("GET", "/api/incidents")).status).toBe(500);
    expect((await call("GET", "/api/session")).status).toBe(200);
    setScenario({ failure: "network" });
    await expect(call("GET", "/api/incidents")).rejects.toThrow();
  });

  it("every example used by the handlers exists in the contract", () => {
    expect(example("confirmBatch", 200, "withNewMatches")).toBeDefined();
    expect(example("getEmailQueue", 200, "paused")).toBeDefined();
  });
});
