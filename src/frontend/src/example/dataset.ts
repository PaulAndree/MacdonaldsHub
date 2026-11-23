import type { components } from "../api/schema";
import { example } from "./contract";

type Row = components["schemas"]["Row"];
type RowFields = components["schemas"]["RowFields"];
type RowPage = components["schemas"]["RowPage"];
type IncidentCore = components["schemas"]["IncidentCore"];
type ClassTotals = components["schemas"]["ClassTotals"];
type BatchSummary = components["schemas"]["BatchSummary"];

/** Which rows a batch of the example holds. Chosen by the name of the uploaded file. */
export type DatasetKind = "large" | "small" | "required-only" | "identical" | "none";

export interface Dataset {
  rows: Row[];
  totals: ClassTotals;
}

const PROVIDERS = ["uber eats", "just eat", "glovo"] as const;
const PREFIX = { "uber eats": "UE", "just eat": "JE", glovo: "GL" } as const;
const BRANCHES = ["centro", "norte", "sur", null] as const;
const AMOUNTS = ["12.50", "0.1234", "8", "31.75", "5.2", "19.99", null, "42.00", "0.05", null];
const DESCRIPTIONS = [null, null, "Falta una bebida", "Pedido frío", null, "Entrega tardía"];

const REASON = {
  existsSame: "Ya existe una incidencia con la misma clave y los mismos datos.",
  existsDifferent: "Ya existe una incidencia con la misma clave pero con datos distintos.",
  repeatedSame: "La clave aparece repetida en el archivo con los mismos datos: se excluyen todas las apariciones.",
  repeatedDifferent: "La clave aparece repetida en el archivo con datos distintos: se excluyen todas las apariciones.",
};

/** Small deterministic generator, so the example is the same on every load. */
function random(seed: number) {
  let state = seed;
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}

type Draft = {
  rowClass: Row["class"];
  fields: RowFields;
  reason: string | null;
  group: number | null;
  comparison: Row["comparison"];
};

function fieldsFor(index: number, next: () => number): RowFields {
  const roll = next();
  const provider = roll < 0.45 ? PROVIDERS[0] : roll < 0.8 ? PROVIDERS[1] : PROVIDERS[2];
  const day = 1 + Math.floor(next() * 20);
  const hasTime = next() < 0.4;
  return {
    provider,
    orderId: `${PREFIX[provider]}-${100000 + index}`,
    incidentDate: `2026-11-${String(day).padStart(2, "0")}`,
    incidentTime: hasTime ? `${String(10 + Math.floor(next() * 12)).padStart(2, "0")}:${next() < 0.5 ? "05" : "40"}` : null,
    branch: BRANCHES[Math.floor(next() * BRANCHES.length)] ?? null,
    claimAmount: AMOUNTS[Math.floor(next() * AMOUNTS.length)] ?? null,
    providerCosts: next() < 0.2 ? "3.00" : null,
    total: next() < 0.15 ? "21.50" : null,
    description: DESCRIPTIONS[Math.floor(next() * DESCRIPTIONS.length)] ?? null,
  };
}

const asCore = (f: RowFields): IncidentCore => ({
  provider: f.provider as IncidentCore["provider"],
  orderId: f.orderId ?? "",
  incidentDate: f.incidentDate ?? "",
  incidentTime: f.incidentTime,
  branch: f.branch,
  claimAmount: f.claimAmount,
  providerCosts: f.providerCosts,
  total: f.total,
  description: f.description,
});

function errorFor(kind: number, fields: RowFields): Pick<Draft, "fields" | "reason"> {
  switch (kind % 6) {
    case 0:
      return { fields: { ...fields, incidentDate: "12/11/2026" }, reason: "La fecha 12/11/2026 no tiene el formato YYYY-MM-DD." };
    case 1:
      return { fields: { ...fields, orderId: null }, reason: "Falta el Order ID." };
    case 2:
      return { fields: { ...fields, provider: "ubereats" }, reason: "El proveedor «ubereats» no es uno de los conocidos." };
    case 3:
      return { fields: { ...fields, branch: "desconocida" }, reason: "La sucursal «desconocida» no es una sucursal conocida." };
    case 4:
      return { fields: { ...fields, claimAmount: "12,50 €" }, reason: "El importe a reclamar debe ser numérico." };
    default:
      return { fields: { ...fields, orderId: "100234" }, reason: "El Order ID debe ser texto, no un número." };
  }
}

function totalsOf(rows: Row[]): ClassTotals {
  const totals: ClassTotals = { new: 0, duplicate: 0, conflict: 0, error: 0 };
  for (const row of rows) totals[row.class] += 1;
  return totals;
}

/** About 500 rows of the four classes, with keys repeated inside the file and conflicts with existing incidents. */
function large(): Dataset {
  const next = random(20261122);
  const drafts: Draft[] = [];
  let index = 0;
  let group = 0;

  for (let i = 0; i < 410; i++) {
    drafts.push({ rowClass: "new", fields: fieldsFor(index++, next), reason: null, group: null, comparison: null });
  }
  // Duplicates: 4 pairs repeated identically inside the file, 52 that already exist.
  for (let pair = 0; pair < 4; pair++) {
    const fields = fieldsFor(index++, next);
    group += 1;
    for (let k = 0; k < 2; k++) {
      drafts.push({ rowClass: "duplicate", fields: { ...fields }, reason: REASON.repeatedSame, group, comparison: null });
    }
  }
  for (let i = 0; i < 52; i++) {
    drafts.push({ rowClass: "duplicate", fields: fieldsFor(index++, next), reason: REASON.existsSame, group: null, comparison: null });
  }
  // Conflicts: 3 keys repeated with different data inside the file, 12 against existing incidents.
  for (let pair = 0; pair < 3; pair++) {
    const fields = fieldsFor(index++, next);
    group += 1;
    drafts.push({ rowClass: "conflict", fields: { ...fields, claimAmount: "10.00" }, reason: REASON.repeatedDifferent, group, comparison: null });
    drafts.push({ rowClass: "conflict", fields: { ...fields, claimAmount: "15.00" }, reason: REASON.repeatedDifferent, group, comparison: null });
  }
  for (let i = 0; i < 12; i++) {
    const fields = fieldsFor(index++, next);
    const differs: (keyof RowFields)[] = i % 3 === 0 ? ["branch", "incidentDate"] : ["claimAmount"];
    const existing: RowFields = { ...fields };
    if (differs.includes("claimAmount")) existing.claimAmount = fields.claimAmount === "9.99" ? "9.98" : "9.99";
    if (differs.includes("branch")) existing.branch = fields.branch === "sur" ? "norte" : "sur";
    if (differs.includes("incidentDate")) existing.incidentDate = "2026-10-30";
    drafts.push({
      rowClass: "conflict",
      fields,
      reason: REASON.existsDifferent,
      group: null,
      comparison: { existing: asCore(existing), differingFields: differs.map(String) },
    });
  }
  for (let i = 0; i < 12; i++) {
    const { fields, reason } = errorFor(i, fieldsFor(index++, next));
    drafts.push({ rowClass: "error", fields, reason, group: null, comparison: null });
  }

  // Shuffle, then number the rows (row 1 is the header) and link repeated keys by row number.
  for (let i = drafts.length - 1; i > 0; i--) {
    const j = Math.floor(next() * (i + 1));
    [drafts[i], drafts[j]] = [drafts[j]!, drafts[i]!];
  }
  const byGroup = new Map<number, number[]>();
  drafts.forEach((draft, i) => {
    if (draft.group !== null) byGroup.set(draft.group, [...(byGroup.get(draft.group) ?? []), i + 2]);
  });
  const rows: Row[] = drafts.map((draft, i) => ({
    rowNumber: i + 2,
    class: draft.rowClass,
    reason: draft.reason,
    fields: draft.fields,
    comparison: draft.comparison,
    repeatedInFile: draft.group === null ? [] : (byGroup.get(draft.group) ?? []).filter((n) => n !== i + 2),
  }));
  return { rows, totals: totalsOf(rows) };
}

function small(): Dataset {
  const rows = example<RowPage>("listBatchRows", 200, "mixed").items;
  return { rows, totals: totalsOf(rows) };
}

/** A file with only the three required columns: every optional value is absent (UI-01). */
function requiredOnly(): Dataset {
  const rows: Row[] = [
    ["uber eats", "UE-300001", "2026-11-18"],
    ["just eat", "JE-300002", "2026-11-18"],
    ["glovo", "GL-300003", "2026-11-19"],
    ["uber eats", "UE-300004", "2026-11-19"],
    ["glovo", "GL-300005", "2026-11-20"],
    ["just eat", "JE-300006", "2026-11-20"],
  ].map(([provider, orderId, incidentDate], i) => ({
    rowNumber: i + 2,
    class: "new" as const,
    reason: null,
    fields: { provider: provider!, orderId: orderId!, incidentDate: incidentDate!, incidentTime: null, branch: null, claimAmount: null, providerCosts: null, total: null, description: null },
    comparison: null,
    repeatedInFile: [],
  }));
  return { rows, totals: totalsOf(rows) };
}

/** A file that repeats one already confirmed: every row is an existing duplicate. */
function identical(): Dataset {
  const next = random(7);
  const rows: Row[] = Array.from({ length: 7 }, (_, i) => ({
    rowNumber: i + 2,
    class: "duplicate" as const,
    reason: REASON.existsSame,
    fields: fieldsFor(400 + i, next),
    comparison: null,
    repeatedInFile: [],
  }));
  return { rows, totals: totalsOf(rows) };
}

const builders: Record<DatasetKind, () => Dataset> = {
  large,
  small,
  "required-only": requiredOnly,
  identical,
  none: () => ({ rows: [], totals: { new: 0, duplicate: 0, conflict: 0, error: 0 } }),
};

const cache = new Map<DatasetKind, Dataset>();

export function datasetOf(kind: DatasetKind): Dataset {
  let dataset = cache.get(kind);
  if (!dataset) {
    dataset = builders[kind]();
    cache.set(kind, dataset);
  }
  return dataset;
}

const sendsEmail = (row: Row) => row.class === "new" && row.fields.provider !== "glovo";

/** What confirming would do, derived from the rows so every screen of the example agrees. */
export function summaryOf(kind: DatasetKind): BatchSummary {
  const { rows, totals } = datasetOf(kind);
  const emails = rows.filter(sendsEmail).length;
  return {
    totals,
    incidentsToCreate: totals.new,
    emailsToGenerate: emails,
    withoutEmail: totals.new - emails,
  };
}

export function excludedOf(kind: DatasetKind) {
  return datasetOf(kind)
    .rows.filter((row) => row.class !== "new")
    .map((row) => ({ rowNumber: row.rowNumber, class: row.class, reason: row.reason ?? "" }));
}

export function firstEmailRow(kind: DatasetKind): Row | undefined {
  return datasetOf(kind).rows.find(sendsEmail);
}
