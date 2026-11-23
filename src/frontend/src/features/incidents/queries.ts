import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { BranchList, IncidentDetail, IncidentFilters, IncidentPage } from "./types";

export const incidentKeys = {
  all: ["incidents"] as const,
  list: (filters: IncidentFilters, page: number) => ["incidents", "list", filters, page] as const,
  detail: (id: string) => ["incidents", "detail", id] as const,
};

export function queryOf(filters: IncidentFilters) {
  return {
    provider: filters.provider,
    branch: filters.branch,
    status: filters.status,
    dateKind: filters.dateKind === "incident" ? undefined : filters.dateKind,
    from: filters.from,
    to: filters.to,
  };
}

/** The address of the export for the filters on screen: the same ones the list uses. */
export function exportPath(filters: IncidentFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(queryOf(filters))) if (value) params.set(key, value);
  const text = params.toString();
  return text ? `/api/incidents/export?${text}` : "/api/incidents/export";
}

export function useIncidents(filters: IncidentFilters, page: number) {
  return useQuery({
    queryKey: incidentKeys.list(filters, page),
    queryFn: () => api.get<IncidentPage>("/api/incidents", { ...queryOf(filters), page, pageSize: 50 }),
    placeholderData: (previous) => previous,
  });
}

export function useIncident(id: string) {
  return useQuery({ queryKey: incidentKeys.detail(id), queryFn: () => api.get<IncidentDetail>(`/api/incidents/${id}`) });
}

/** Branch names for the filter. */
export function useBranchOptions() {
  return useQuery({
    queryKey: ["branch-options"],
    queryFn: () => api.get<BranchList>("/api/branches"),
    staleTime: 5 * 60_000,
    retry: false,
  });
}
