import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type Metrics = components["schemas"]["Metrics"];
export type ChannelMetrics = components["schemas"]["ChannelMetrics"];

export interface MetricsFilters {
  dateKind: string;
  from: string;
  to: string;
  provider: string;
  branch: string;
}

/** The dashboard counts claims, so by default it counts by the date of the claim. */
export const DEFAULT_METRICS_FILTERS: MetricsFilters = { dateKind: "claim", from: "", to: "", provider: "", branch: "" };

export function useMetrics(filters: MetricsFilters) {
  return useQuery({
    queryKey: ["metrics", filters],
    queryFn: () => api.get<Metrics>("/api/metrics", { ...filters }),
    placeholderData: (previous) => previous,
  });
}
