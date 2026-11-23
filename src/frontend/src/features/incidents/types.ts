import type { components } from "../../api/schema";

export type Incident = components["schemas"]["Incident"];
export type IncidentStatus = components["schemas"]["IncidentStatus"];
export type IncidentPage = components["schemas"]["IncidentPage"];
export type IncidentDetail = components["schemas"]["IncidentDetail"];
export type HistoryEntry = components["schemas"]["HistoryEntry"];
export type IncidentCore = components["schemas"]["IncidentCore"];
export type BranchList = components["schemas"]["BranchList"];

export interface IncidentFilters {
  provider: string;
  branch: string;
  status: string;
  dateKind: string;
  from: string;
  to: string;
}

export const EMPTY_FILTERS: IncidentFilters = { provider: "", branch: "", status: "", dateKind: "incident", from: "", to: "" };
