import { HttpResponse, delay, http } from "msw";
import type { components } from "../api/schema";
import { type Operation, example, operations, successStatus } from "./contract";
import { datasetOf, excludedOf, firstEmailRow, summaryOf } from "./dataset";
import { excludedSheet, incidentsSheet } from "./exports";
import {
  IncidentError,
  addFromBatch,
  checkManual,
  claim,
  correct,
  createManual,
  detailOf,
  filterIncidents,
  page as paginate,
  recordResult,
} from "./incidents";
import { requiredPermission } from "./permissions";
import { computeMetrics } from "./metrics";
import { buildXlsx } from "./xlsx";
import { XLSX_TYPE, sampleXlsx } from "./sampleXlsx";
import { type Scenario, getScenario } from "./scenario";
import {
  type BatchRecord,
  UNCONFIRMED,
  datasetFor,
  getStore,
  outcomeFor,
  pendingRecord,
  refresh,
} from "./state";

type Session = components["schemas"]["Session"];
type ConfirmationResult = components["schemas"]["ConfirmationResult"];

interface Context {
  op: Operation;
  request: Request;
  params: Record<string, string | readonly string[] | undefined>;
  scenario: Scenario;
}

type Override = (ctx: Context) => Promise<Response> | Response;

const json = (body: unknown, status = 200) => HttpResponse.json(body as never, { status });

function sessionFor(scenario: Scenario): Session {
  return example<Session>("getSession", 200, scenario.role === "administrator" ? "administrator" : "globalManager");
}

function firstParam(value: string | readonly string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : String(value ?? "");
}

function recordOrNotFound(id: string): BatchRecord | null {
  const record = getStore().batches.get(id);
  return record ? refresh(record) : null;
}

const notFound = () => json(example("getBatch", 404), 404);

const xlsxResponse = (bytes: Uint8Array, fileName: string) =>
  new HttpResponse(bytes as unknown as BodyInit, {
    status: 200,
    headers: { "Content-Type": XLSX_TYPE, "Content-Disposition": `attachment; filename="${fileName}"` },
  });

/** Runs an incident operation and turns a refusal into the error response the contract documents. */
async function incidentAction(run: () => unknown, status = 200): Promise<Response> {
  try {
    return json(await run(), status);
  } catch (error) {
    if (error instanceof IncidentError) return json({ code: error.code, message: error.message }, error.status);
    throw error;
  }
}

function filtersOf(request: Request) {
  const q = new URL(request.url).searchParams;
  return {
    provider: q.get("provider"),
    branch: q.get("branch"),
    status: q.get("status"),
    dateKind: q.get("dateKind"),
    from: q.get("from"),
    to: q.get("to"),
  };
}

/** Handlers with their own logic; every other operation answers from the contract examples. */
const overrides: Record<string, Override> = {
  getSession: ({ scenario }) => json(sessionFor(scenario)),

  createBatch: async ({ request }) => {
    const body = (await request.json()) as components["schemas"]["CreateBatchRequest"];
    const pending = pendingRecord();
    if (pending) {
      const conflict = example<components["schemas"]["Error"]>("createBatch", 409, "pendingBatchExists");
      conflict.details = { batchId: pending.batch.id };
      return json(conflict, 409);
    }
    const store = getStore();
    const outcome = outcomeFor(body.fileName);
    const id = `lote-${String(store.counter++).padStart(4, "0")}`;
    const created = example<components["schemas"]["BatchUpload"]>("createBatch", 201, "created");
    created.batch = {
      ...created.batch,
      id,
      fileName: body.fileName,
      createdAt: new Date().toISOString(),
    };
    created.upload.url = `https://example.invalid/uploads/${id}?sp=c`;
    store.batches.set(id, {
      batch: created.batch,
      outcome,
      dataset: datasetFor(outcome),
      processingUntil: null,
      result: null,
    });
    return json(created, 201);
  },

  getPendingBatch: () => {
    const pending = pendingRecord();
    if (!pending) return new HttpResponse(null, { status: 204 });
    return json(refresh(pending).batch);
  },

  completeUpload: ({ params, scenario }) => {
    const record = recordOrNotFound(firstParam(params.batchId));
    if (!record) return notFound();
    record.batch = { ...record.batch, state: "processing" };
    record.processingUntil = Date.now() + scenario.processingMs;
    return json(record.batch, 202);
  },

  getBatch: ({ params }) => {
    const record = recordOrNotFound(firstParam(params.batchId));
    return record ? json(record.batch) : notFound();
  },

  listBatchRows: ({ params, request }) => {
    const record = recordOrNotFound(firstParam(params.batchId));
    if (!record) return notFound();
    const query = new URL(request.url).searchParams;
    const rowClass = query.get("class");
    const page = Math.max(1, Number(query.get("page") ?? 1));
    const pageSize = Math.min(200, Math.max(1, Number(query.get("pageSize") ?? 50)));
    const { rows, totals } = datasetOf(record.dataset);
    const matching = rowClass ? rows.filter((row) => row.class === rowClass) : rows;
    return json({
      items: matching.slice((page - 1) * pageSize, page * pageSize),
      page,
      pageSize,
      total: matching.length,
      totalsByClass: totals,
    });
  },

  getConfirmationSummary: ({ params }) => {
    const record = recordOrNotFound(firstParam(params.batchId));
    if (!record) return notFound();
    const summary = example<components["schemas"]["ConfirmationSummary"]>("getConfirmationSummary", 200);
    const totals = summaryOf(record.dataset);
    return json({
      ...summary,
      batchId: record.batch.id,
      reviewedVersion: record.batch.reviewedVersion ?? summary.reviewedVersion,
      incidentsToCreate: totals.incidentsToCreate,
      emailsToGenerate: totals.emailsToGenerate,
      withoutEmail: totals.withoutEmail,
      excluded: totals.totals.duplicate + totals.totals.conflict + totals.totals.error,
    });
  },

  listIncidents: ({ request, scenario }) => {
    if (scenario.emptyData) return json(example("listIncidents", 200, "empty"));
    const q = new URL(request.url).searchParams;
    const pageNumber = Math.max(1, Number(q.get("page") ?? 1));
    const pageSize = Math.min(200, Math.max(1, Number(q.get("pageSize") ?? 50)));
    return json(paginate(filterIncidents(getStore().incidents, filtersOf(request)), pageNumber, pageSize));
  },

  exportIncidents: ({ request }) =>
    xlsxResponse(buildXlsx("Incidencias", incidentsSheet(filterIncidents(getStore().incidents, filtersOf(request)))), "incidencias.xlsx"),

  getMetrics: ({ request, scenario }) => {
    if (scenario.emptyData) return json(example("getMetrics", 200, "empty"));
    const q = new URL(request.url).searchParams;
    return json(
      computeMetrics(
        getStore().incidents,
        { dateKind: q.get("dateKind") ?? "claim", from: q.get("from"), to: q.get("to"), provider: q.get("provider"), branch: q.get("branch") },
        sessionFor(scenario).environment,
      ),
    );
  },

  getIncident: ({ params }) => {
    const detail = detailOf(getStore().incidents, firstParam(params.incidentId));
    return detail ? json(detail) : json(example("getBatch", 404), 404);
  },

  checkManualIncident: async ({ request }) =>
    json(checkManual(getStore().incidents, (await request.json()) as components["schemas"]["IncidentCore"])),

  createManualIncident: async ({ request, scenario }) =>
    incidentAction(
      async () => createManual(getStore().incidents, (await request.json()) as components["schemas"]["IncidentCore"], sessionFor(scenario).identifier),
      201,
    ),

  claimGlovoIncident: async ({ params, request, scenario }) => {
    const body = (await request.json()) as components["schemas"]["ClaimRequest"];
    return incidentAction(() => claim(getStore().incidents, firstParam(params.incidentId), body.claimDate, sessionFor(scenario).identifier));
  },

  recordIncidentResult: async ({ params, request, scenario }) => {
    const body = (await request.json()) as components["schemas"]["ResultRequest"];
    return incidentAction(() => recordResult(getStore().incidents, firstParam(params.incidentId), body, sessionFor(scenario).identifier));
  },

  correctIncidentResult: async ({ params, request, scenario }) => {
    const body = (await request.json()) as components["schemas"]["CorrectionRequest"];
    const id = firstParam(params.incidentId);
    return incidentAction(() => {
      correct(getStore().incidents, id, body, sessionFor(scenario).identifier);
      return detailOf(getStore().incidents, id);
    });
  },

  downloadExcludedReport: ({ params }) => {
    const record = recordOrNotFound(firstParam(params.batchId));
    if (!record) return notFound();
    return xlsxResponse(buildXlsx("Filas excluidas", excludedSheet(record.dataset)), "informe-filas-excluidas.xlsx");
  },

  discardUnconfirmedBatches: () => {
    const discarded: string[] = [];
    for (const record of getStore().batches.values()) {
      if (UNCONFIRMED.includes(refresh(record).batch.state)) {
        record.batch = { ...record.batch, state: "discarded", reviewedVersion: null, summary: null };
        discarded.push(record.batch.id);
      }
    }
    return json({ discarded: discarded.length, batchIds: discarded });
  },

  discardBatch: ({ params }) => {
    const record = recordOrNotFound(firstParam(params.batchId));
    if (!record) return notFound();
    if (record.batch.state === "confirmed" || record.batch.state === "completed") {
      return json(example("discardBatch", 409, "alreadyConfirmed"), 409);
    }
    record.batch = { ...record.batch, state: "discarded", reviewedVersion: null, summary: null };
    return json(record.batch);
  },

  confirmBatch: async ({ params, request, scenario }) => {
    const record = recordOrNotFound(firstParam(params.batchId));
    if (!record) return notFound();
    const { reviewedVersion } = (await request.json()) as components["schemas"]["ConfirmRequest"];
    if (record.batch.state === "discarded") return json(example("confirmBatch", 409, "discarded"), 409);
    if (record.result) {
      return json({ ...record.result, excluded: [], excludedAtConfirmation: [], alreadyConfirmed: true });
    }
    if (record.batch.state !== "in_review") {
      return json({ code: "batch_not_in_review", message: "El lote todavía no está listo para confirmarse." }, 409);
    }
    if (reviewedVersion !== record.batch.reviewedVersion) {
      return json(example("confirmBatch", 422, "versionMismatch"), 422);
    }
    const totals = summaryOf(record.dataset);
    const result = example<ConfirmationResult>("confirmBatch", 200, "confirmed");
    result.batchId = record.batch.id;
    result.confirmedAt = new Date().toISOString();
    result.createdIncidents = totals.incidentsToCreate;
    result.pendingEmails = totals.emailsToGenerate;
    result.withoutEmail = totals.withoutEmail;
    result.excluded = excludedOf(record.dataset);
    result.excludedAtConfirmation = [];
    const overtaken = scenario.matchesAtConfirmation ? firstEmailRow(record.dataset) : undefined;
    if (overtaken) {
      // Another batch confirmed this key while it was being reviewed (RF-10).
      result.createdIncidents -= 1;
      result.pendingEmails -= 1;
      result.excludedAtConfirmation = [
        { rowNumber: overtaken.rowNumber, class: "duplicate", reason: "Otro lote confirmó esta incidencia mientras se revisaba." },
      ];
    }
    record.result = result;
    record.batch = { ...record.batch, state: "confirmed" };
    addFromBatch(getStore().incidents, record.batch.id, record.dataset, overtaken?.rowNumber);
    return json(result);
  },

  getEmailQueue: ({ scenario, request }) => {
    const paused = getStore().queuePaused;
    const view = example<{ items: { state: string; batchId: string }[]; total: number }>(
      "getEmailQueue",
      200,
      paused ? "paused" : scenario.queueView,
    );
    // The filters narrow the list only; the totals and batches always describe the whole queue.
    const url = new URL(request.url);
    const state = url.searchParams.get("state");
    const batchId = url.searchParams.get("batchId");
    view.items = view.items.filter((item) => (!state || item.state === state) && (!batchId || item.batchId === batchId));
    view.total = view.items.length;
    return json(view);
  },

  pauseEmailQueue: () => {
    getStore().queuePaused = true;
    return json(example("pauseEmailQueue", 200));
  },

  resumeEmailQueue: () => {
    getStore().queuePaused = false;
    return json(example("resumeEmailQueue", 200));
  },
};

/** Answers from the contract: the first success example, or the `empty` one when the scenario asks. */
function fromContract({ op, scenario }: Context): Response {
  const status = successStatus(op);
  if (op.binary) {
    return new HttpResponse(sampleXlsx() as unknown as BodyInit, {
      status,
      headers: {
        "Content-Type": XLSX_TYPE,
        "Content-Disposition": 'attachment; filename="ejemplo.xlsx"',
      },
    });
  }
  const list = op.examples.get(status);
  if (!list) return new HttpResponse(null, { status });
  const chosen = (scenario.emptyData && list.find((e) => e.name === "empty")) || list[0]!;
  return json(structuredClone(chosen.value), status);
}

async function handle(ctx: Context): Promise<Response> {
  const { op, scenario } = ctx;
  await delay(scenario.latencyMs);

  if (op.id !== "getSession") {
    if (scenario.failure === "network") return HttpResponse.error();
    if (scenario.failure === "server") {
      return json({ code: "server_error", message: "Error interno de ejemplo." }, 500);
    }
  }

  const needed = requiredPermission[op.id];
  if (needed && !sessionFor(scenario).permissions.includes(needed)) {
    return json(example("getSession", 403), 403);
  }
  return (overrides[op.id] ?? fromContract)(ctx);
}

const contractHandlers = operations.map((op) =>
  http[op.method](op.pattern, ({ request, params }) =>
    handle({ op, request, params, scenario: getScenario() }),
  ),
);

/** The temporary upload address the contract examples hand out. Storage is simulated here too. */
const uploadHandler = http.put("https://example.invalid/uploads/:id", async () => {
  const scenario = getScenario();
  await delay(scenario.latencyMs);
  if (scenario.failure === "network") return HttpResponse.error();
  return new HttpResponse(null, { status: scenario.failure === "storage" ? 403 : 201 });
});

export const handlers = [uploadHandler, ...contractHandlers];
