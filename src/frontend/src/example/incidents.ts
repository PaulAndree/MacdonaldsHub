import type { components } from "../api/schema";
import { example } from "./contract";
import { datasetOf } from "./dataset";
import type { DatasetKind } from "./dataset";

type Incident = components["schemas"]["Incident"];
type IncidentCore = components["schemas"]["IncidentCore"];
type IncidentDetail = components["schemas"]["IncidentDetail"];
type IncidentPage = components["schemas"]["IncidentPage"];
type HistoryEntry = components["schemas"]["HistoryEntry"];
type ManualCheckResult = components["schemas"]["ManualCheckResult"];
type ResultRequest = components["schemas"]["ResultRequest"];
type CorrectionRequest = components["schemas"]["CorrectionRequest"];

export interface IncidentStore {
  items: Incident[];
  history: Map<string, HistoryEntry[]>;
  counter: number;
}

/** A refusal the handler turns into an HTTP error. */
export class IncidentError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const now = () => new Date().toISOString();

export function seedIncidents(): IncidentStore {
  const items = example<IncidentPage>("listIncidents", 200, "default").items;
  const history = new Map<string, HistoryEntry[]>();
  const withHistory = [
    example<IncidentDetail>("getIncident", 200, "claimedByEmail"),
    example<IncidentDetail>("getIncident", 200, "sendError"),
    example<IncidentDetail>("getIncident", 200, "partialRecovery"),
    example<IncidentDetail>("getIncident", 200, "corrected"),
  ];
  for (const detail of withHistory) {
    history.set(detail.incident.id, detail.history);
    if (!items.some((i) => i.id === detail.incident.id)) items.push(detail.incident);
  }
  // An incident claimed by email whose amount was never given: the dashboard must flag it as incomplete.
  const withoutAmount: Incident = {
    id: "inc-006", batchId: "lote-0005", provider: "just eat", orderId: "JE-44200", incidentDate: "2026-11-13", incidentTime: null,
    branch: "centro", claimAmount: null, providerCosts: null, total: null, description: null,
    status: "claimed", channel: "email", claimDate: "2026-11-19", recoveryDate: null, recoveredAmount: null, result: null,
  };
  items.push(withoutAmount);
  history.set("inc-006", [
    { at: "2026-11-13T09:00:00Z", actor: "system", kind: "imported", field: "status", previousValue: null, newValue: "pending_send", reason: null },
    { at: "2026-11-19T10:00:00Z", actor: "system", kind: "email_result", field: "status", previousValue: "pending_send", newValue: "claimed", reason: null },
  ]);
  for (const incident of items) {
    if (!history.has(incident.id)) {
      history.set(incident.id, [
        { at: "2026-11-12T08:00:00Z", actor: "system", kind: "imported", field: "status", previousValue: null, newValue: incident.status, reason: null },
      ]);
    }
  }
  return { items, history, counter: 200 };
}

export interface Filters {
  provider?: string | null;
  branch?: string | null;
  status?: string | null;
  dateKind?: string | null;
  from?: string | null;
  to?: string | null;
}

function dateOf(incident: Incident, kind: string): string | null {
  if (kind === "claim") return incident.claimDate;
  if (kind === "recovery") return incident.recoveryDate;
  return incident.incidentDate;
}

export function filterIncidents(store: IncidentStore, filters: Filters): Incident[] {
  const kind = filters.dateKind ?? "incident";
  return store.items
    .filter((i) => !filters.provider || i.provider === filters.provider)
    .filter((i) => !filters.branch || (filters.branch === "none" ? i.branch === null : i.branch === filters.branch))
    .filter((i) => !filters.status || i.status === filters.status)
    .filter((i) => {
      if (!filters.from && !filters.to) return true;
      const date = dateOf(i, kind);
      if (date === null) return false;
      return (!filters.from || date >= filters.from) && (!filters.to || date <= filters.to);
    })
    .sort((a, b) => (a.incidentDate === b.incidentDate ? b.id.localeCompare(a.id) : b.incidentDate.localeCompare(a.incidentDate)));
}

export function page<T>(items: T[], pageNumber: number, pageSize: number) {
  return { items: items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize), page: pageNumber, pageSize, total: items.length };
}

export function detailOf(store: IncidentStore, id: string): IncidentDetail | null {
  const incident = store.items.find((i) => i.id === id);
  return incident ? { incident, history: store.history.get(id) ?? [] } : null;
}

const RELEVANT = ["incidentDate", "incidentTime", "branch", "claimAmount", "providerCosts", "total", "description"] as const;

const coreOf = (i: Incident): IncidentCore => ({
  provider: i.provider,
  orderId: i.orderId,
  incidentDate: i.incidentDate,
  incidentTime: i.incidentTime,
  branch: i.branch,
  claimAmount: i.claimAmount,
  providerCosts: i.providerCosts,
  total: i.total,
  description: i.description,
});

/** Same provider and order ID: identical relevant fields is a duplicate, any difference is a conflict. */
export function checkManual(store: IncidentStore, core: IncidentCore): ManualCheckResult {
  const found = store.items.find((i) => i.provider === core.provider && i.orderId === core.orderId);
  if (!found) return { outcome: "new", existing: null, differingFields: [] };
  const differing = RELEVANT.filter((field) => found[field] !== core[field]);
  return { outcome: differing.length === 0 ? "duplicate" : "conflict", existing: coreOf(found), differingFields: [...differing] };
}

const channelOf = (provider: string): Incident["channel"] => (provider === "glovo" ? "glovo" : "email");

function add(store: IncidentStore, incident: Incident, actor: string, at = now()) {
  store.items.push(incident);
  store.history.set(incident.id, [{ at, actor, kind: "imported", field: "status", previousValue: null, newValue: incident.status, reason: null }]);
}

/** A manual entry creates the incident without any email (P-12 is pending). */
export function createManual(store: IncidentStore, core: IncidentCore, actor: string): Incident {
  if (checkManual(store, core).outcome !== "new") {
    throw new IncidentError(409, "incident_exists", "Ya existe una incidencia con ese proveedor y ese Order ID.");
  }
  const incident: Incident = {
    ...core,
    id: `inc-${store.counter++}`,
    batchId: null,
    // Uber Eats and Just Eat get their email; Glovo is claimed by hand (P-12).
    status: core.provider === "glovo" ? "imported_no_email" : "pending_send",
    channel: channelOf(core.provider),
    claimDate: null,
    recoveryDate: null,
    recoveredAmount: null,
    result: null,
  };
  add(store, incident, actor);
  return incident;
}

/** Confirming a batch creates its new incidents: with an email pending for Uber Eats and Just Eat, none for Glovo. */
export function addFromBatch(store: IncidentStore, batchId: string, kind: DatasetKind, skipRow?: number): void {
  for (const row of datasetOf(kind).rows) {
    if (row.class !== "new" || row.rowNumber === skipRow) continue;
    const f = row.fields;
    const incident: Incident = {
      id: `inc-${store.counter++}`,
      batchId,
      provider: f.provider as Incident["provider"],
      orderId: f.orderId ?? "",
      incidentDate: f.incidentDate ?? "",
      incidentTime: f.incidentTime,
      branch: f.branch,
      claimAmount: f.claimAmount,
      providerCosts: f.providerCosts,
      total: f.total,
      description: f.description,
      status: f.provider === "glovo" ? "imported_no_email" : "pending_send",
      channel: channelOf(f.provider ?? ""),
      claimDate: null,
      recoveryDate: null,
      recoveredAmount: null,
      result: null,
    };
    add(store, incident, "system");
  }
}

function find(store: IncidentStore, id: string): Incident {
  const incident = store.items.find((i) => i.id === id);
  if (!incident) throw new IncidentError(404, "not_found", "No se encontró el elemento solicitado.");
  return incident;
}

function log(store: IncidentStore, id: string, entry: Omit<HistoryEntry, "at">) {
  store.history.set(id, [...(store.history.get(id) ?? []), { at: now(), ...entry }]);
}

/** An incident without email (Glovo, or a manual entry) is claimed outside the application. */
export function claim(store: IncidentStore, id: string, claimDate: string, actor: string): Incident {
  const incident = find(store, id);
  if (incident.status !== "imported_no_email") {
    throw new IncidentError(409, "claim_not_available", "Esta incidencia no se puede reclamar de forma manual porque tiene un correo asociado o ya está reclamada.");
  }
  incident.status = "claimed";
  incident.claimDate = claimDate;
  log(store, id, { actor, kind: "claim", field: "status", previousValue: "imported_no_email", newValue: "claimed", reason: null });
  log(store, id, { actor, kind: "claim", field: "claimDate", previousValue: null, newValue: claimDate, reason: null });
  return incident;
}

const statusOf = (result: ResultRequest["result"]): Incident["status"] => (result === "resolved" ? "resolved" : "rejected");

/** The result of a claimed incident, with the recovered amount recorded explicitly (partial or full). */
export function recordResult(store: IncidentStore, id: string, request: ResultRequest, actor: string): Incident {
  const incident = find(store, id);
  if (incident.status !== "claimed") {
    throw new IncidentError(409, "incident_not_claimed", "Solo se puede registrar el resultado de una incidencia reclamada. Para cambiar uno ya registrado use una corrección.");
  }
  const previous = incident.status;
  incident.status = statusOf(request.result);
  incident.result = request.result;
  incident.recoveredAmount = request.recoveredAmount;
  incident.recoveryDate = request.recoveryDate;
  log(store, id, { actor, kind: "result", field: "status", previousValue: previous, newValue: incident.status, reason: null });
  if (request.recoveredAmount !== null) log(store, id, { actor, kind: "result", field: "recoveredAmount", previousValue: null, newValue: request.recoveredAmount, reason: null });
  if (request.recoveryDate !== null) log(store, id, { actor, kind: "result", field: "recoveryDate", previousValue: null, newValue: request.recoveryDate, reason: null });
  return incident;
}

/** Corrects a recorded result. Each changed value is a history entry with the reason; the import and the emails are untouched. */
export function correct(store: IncidentStore, id: string, request: CorrectionRequest, actor: string): Incident {
  const incident = find(store, id);
  if (incident.result === null) {
    throw new IncidentError(409, "no_result_to_correct", "Esta incidencia todavía no tiene un resultado registrado que corregir.");
  }
  const changes: [HistoryEntry["field"], string | null, string | null][] = [];
  if (incident.result !== request.result) changes.push(["result", incident.result, request.result]);
  if (incident.recoveredAmount !== request.recoveredAmount) changes.push(["recoveredAmount", incident.recoveredAmount, request.recoveredAmount]);
  if (incident.recoveryDate !== request.recoveryDate) changes.push(["recoveryDate", incident.recoveryDate, request.recoveryDate]);
  incident.result = request.result;
  incident.status = statusOf(request.result);
  incident.recoveredAmount = request.recoveredAmount;
  incident.recoveryDate = request.recoveryDate;
  for (const [field, previousValue, newValue] of changes) {
    log(store, id, { actor, kind: "correction", field, previousValue, newValue, reason: request.reason });
  }
  return incident;
}
