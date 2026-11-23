import type { components } from "../api/schema";
import { example } from "./contract";
import { type DatasetKind, summaryOf } from "./dataset";
import { type IncidentStore, seedIncidents } from "./incidents";
import { getScenario } from "./scenario";

type Batch = components["schemas"]["Batch"];
type ConfirmationResult = components["schemas"]["ConfirmationResult"];

/** What the example does with a file, decided by its name so every walkthrough can be reproduced. */
export type Outcome =
  | "review"
  | "required-only"
  | "identical"
  | "missing_header"
  | "multiple_sheets"
  | "corrupt";

export interface BatchRecord {
  batch: Batch;
  outcome: Outcome;
  /** The rows this batch holds. */
  dataset: DatasetKind;
  /** When the batch leaves `processing`; `null` once it has. */
  processingUntil: number | null;
  result: ConfirmationResult | null;
}

export interface Store {
  batches: Map<string, BatchRecord>;
  counter: number;
  queuePaused: boolean;
  incidents: IncidentStore;
  /** The scenario this store was seeded for. */
  seededPending: boolean;
}

export const UNCONFIRMED: Batch["state"][] = ["uploaded", "processing", "in_review"];

function seed(): Store {
  const batches = new Map<string, BatchRecord>();
  const confirmed = example<Batch>("getBatch", 200, "confirmed");
  batches.set(confirmed.id, { batch: confirmed, outcome: "review", dataset: "none", processingUntil: null, result: null });
  const pending = getScenario().pendingBatch;
  if (pending) {
    const inReview = example<Batch>("getPendingBatch", 200, "inReview");
    batches.set(inReview.id, { batch: inReview, outcome: "review", dataset: "small", processingUntil: null, result: null });
  }
  return { batches, counter: 7, queuePaused: false, incidents: seedIncidents(), seededPending: pending };
}

let store: Store | null = null;

/** The example's memory. It resets when the scenario's starting data changes, and on reload. */
export function getStore(): Store {
  if (!store || store.seededPending !== getScenario().pendingBatch) store = seed();
  return store;
}

export function resetStore(): void {
  store = null;
}

/** The rows a file of each outcome holds (rejected files hold none). */
export function datasetFor(outcome: Outcome): DatasetKind {
  if (outcome === "review") return "large";
  if (outcome === "required-only") return "required-only";
  if (outcome === "identical") return "identical";
  return "none";
}

export function outcomeFor(fileName: string): Outcome {
  const name = fileName.toLowerCase();
  if (name.includes("sin-order-id")) return "missing_header";
  if (name.includes("solo-obligatorios")) return "required-only";
  if (name.includes("dos-hojas")) return "multiple_sheets";
  if (name.includes("protegido") || name.includes("danado")) return "corrupt";
  if (name.includes("identica")) return "identical";
  return "review";
}

/** The batch the user has not confirmed, if any (at most one per user). */
export function pendingRecord(): BatchRecord | undefined {
  return [...getStore().batches.values()].find((r) => UNCONFIRMED.includes(r.batch.state));
}

/** Moves a batch out of `processing` once its time is up, then returns it. */
export function refresh(record: BatchRecord): BatchRecord {
  if (record.batch.state !== "processing" || record.processingUntil === null) return record;
  if (Date.now() < record.processingUntil) return record;
  const { id, fileName, createdAt } = record.batch;
  const finalName =
    record.outcome === "missing_header"
      ? "rejectedMissingHeader"
      : record.outcome === "multiple_sheets"
        ? "rejectedMultipleWorksheets"
        : record.outcome === "corrupt"
          ? "rejectedCorruptFile"
          : record.outcome === "identical"
            ? "inReviewIdenticalFile"
            : "inReview";
  const final = { ...example<Batch>("getBatch", 200, finalName), id, fileName, createdAt };
  // The totals come from the rows, so the summary, the preview and the confirmation always agree.
  record.batch = final.state === "in_review" ? { ...final, summary: summaryOf(record.dataset) } : final;
  record.processingUntil = null;
  return record;
}
