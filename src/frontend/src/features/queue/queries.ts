import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type QueueView = components["schemas"]["QueueView"];
export type QueueStatus = components["schemas"]["QueueStatus"];
export type QueueEntry = components["schemas"]["QueueEntry"];
export type EmailTotals = components["schemas"]["EmailTotals"];
export type EmailState = components["schemas"]["EmailState"];

export interface QueueFilters {
  state: string;
  batchId: string;
}

export const queueKey = ["email-queue"] as const;
const PAGE_SIZE = 50;

/** The queue changes while it is open, so it is refreshed every few seconds. */
export function useQueue(filters: QueueFilters, page: number) {
  return useQuery({
    queryKey: [...queueKey, filters, page],
    queryFn: () =>
      api.get<QueueView>("/api/email-queue", {
        state: filters.state || undefined,
        batchId: filters.batchId || undefined,
        page,
        pageSize: PAGE_SIZE,
      }),
    placeholderData: (previous) => previous,
    refetchInterval: 10_000,
  });
}

/** Pause or resume. The new status is what the API answers, never what the screen assumes. */
export const changeQueue = (kind: "pause" | "resume") => api.post<QueueStatus>(`/api/email-queue/${kind}`);
