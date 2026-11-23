import type { components } from "../../api/schema";

export type Batch = components["schemas"]["Batch"];
export type BatchState = components["schemas"]["BatchState"];
export type BatchUpload = components["schemas"]["BatchUpload"];
export type Row = components["schemas"]["Row"];
export type RowClass = components["schemas"]["RowClass"];
export type RowPage = components["schemas"]["RowPage"];
export type ConfirmationSummary = components["schemas"]["ConfirmationSummary"];
export type ConfirmationResult = components["schemas"]["ConfirmationResult"];
export type DiscardResult = components["schemas"]["DiscardResult"];

/** A batch the user has not confirmed. There is at most one per user. */
export const UNCONFIRMED: BatchState[] = ["uploaded", "processing", "in_review"];
export const isUnconfirmed = (batch: Batch) => UNCONFIRMED.includes(batch.state);
