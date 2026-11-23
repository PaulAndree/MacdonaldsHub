import { skipToken, useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { Batch, ConfirmationResult, ConfirmationSummary, RowClass, RowPage } from "./types";

export const batchKeys = {
  pending: ["batches", "pending"] as const,
  batch: (id: string) => ["batches", id] as const,
  rows: (id: string, rowClass: RowClass | "all", page: number) => ["batches", id, "rows", rowClass, page] as const,
  summary: (id: string) => ["batches", id, "summary"] as const,
  result: (id: string) => ["batches", id, "result"] as const,
};

/** The user's unconfirmed batch, or `null`. Shown when they return; there is no expiry. */
export function usePendingBatch(enabled = true) {
  return useQuery({
    queryKey: batchKeys.pending,
    queryFn: async () => (await api.get<Batch | undefined>("/api/batches/pending")) ?? null,
    enabled,
    retry: false,
    retryOnMount: false,
  });
}

/** A batch. While it is being uploaded or processed it is checked again every second. */
export function useBatch(id: string) {
  return useQuery({
    queryKey: batchKeys.batch(id),
    queryFn: () => api.get<Batch>(`/api/batches/${id}`),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === "uploaded" || state === "processing" ? 1000 : false;
    },
  });
}

export function useBatchRows(id: string, rowClass: RowClass | "all", page: number, enabled: boolean) {
  return useQuery({
    queryKey: batchKeys.rows(id, rowClass, page),
    queryFn: () =>
      api.get<RowPage>(`/api/batches/${id}/rows`, {
        class: rowClass === "all" ? undefined : rowClass,
        page,
        pageSize: 50,
      }),
    enabled,
    placeholderData: (previous) => previous,
  });
}

export function useConfirmationSummary(id: string, enabled: boolean) {
  return useQuery({
    queryKey: batchKeys.summary(id),
    queryFn: () => api.get<ConfirmationSummary>(`/api/batches/${id}/confirmation-summary`),
    enabled,
  });
}

/** The stored result of a confirmation, once there is one. It is only ever set by the confirmation itself. */
export function useConfirmationResult(id: string) {
  return useQuery<ConfirmationResult>({ queryKey: batchKeys.result(id), queryFn: skipToken });
}
