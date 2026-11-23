import type { components } from "../api/schema";
import { daysBetween, ratio, sumDecimals } from "./decimal";
import type { IncidentStore } from "./incidents";

type Incident = components["schemas"]["Incident"];
type Metrics = components["schemas"]["Metrics"];
type Environment = components["schemas"]["Environment"];

/** The day the example "is". Fixed, so the ages in the example do not change from one day to the next. */
export const EXAMPLE_TODAY = "2026-11-22";

export interface MetricsQuery {
  dateKind: string;
  from: string | null;
  to: string | null;
  provider: string | null;
  branch: string | null;
}

const dateOf = (incident: Incident, kind: string): string | null =>
  kind === "recovery" ? incident.recoveryDate : kind === "incident" ? incident.incidentDate : incident.claimDate;

function figures(group: Incident[]) {
  const claimed = group.map((i) => i.claimAmount).filter((v): v is string => v !== null);
  const recovered = group.map((i) => i.recoveredAmount).filter((v): v is string => v !== null);
  return {
    claimedCount: group.length,
    claimedAmount: sumDecimals(claimed),
    recoveredCount: recovered.length,
    recoveredAmount: sumDecimals(recovered),
    incompleteCount: group.length - claimed.length,
  };
}

/**
 * The dashboard figures of the example, worked out from the incidents it holds. Only claimed incidents
 * count. Amounts are summed exactly, an absent amount is left out of the sum and counted as
 * incomplete (never as zero). The rate and the age are the example criteria of P-04, not approved ones.
 * This imitates the backend; the real calculation is defined in change 2.
 */
export function computeMetrics(store: IncidentStore, query: MetricsQuery, environment: Environment): Metrics {
  const kind = query.dateKind || "claim";
  const byFilters = store.items
    .filter((i) => !query.provider || i.provider === query.provider)
    .filter((i) => !query.branch || (query.branch === "none" ? i.branch === null : i.branch === query.branch));

  const claimedInRange = byFilters
    .filter((i) => i.claimDate !== null)
    .filter((i) => {
      if (!query.from && !query.to) return true;
      const date = dateOf(i, kind);
      return date !== null && (!query.from || date >= query.from) && (!query.to || date <= query.to);
    });

  const channels = (["email", "glovo"] as const).map((channel) => {
    const group = claimedInRange.filter((i) => i.channel === channel);
    const f = figures(group);
    return {
      channel,
      ...f,
      recoveryRate: f.claimedAmount !== null && f.recoveredAmount !== null ? ratio(f.recoveredAmount, f.claimedAmount) : null,
    };
  });

  const keys = [...new Set(claimedInRange.map((i) => `${i.provider}|${i.branch ?? ""}`))].sort();
  const breakdown = keys.map((key) => {
    const [provider, branch] = key.split("|") as [Incident["provider"], string];
    const group = claimedInRange.filter((i) => i.provider === provider && (i.branch ?? "") === branch);
    return { provider, branch: branch === "" ? null : branch, ...figures(group) };
  });

  const pendingClaims = byFilters
    .filter((i) => i.status === "claimed" && i.claimDate !== null)
    .map((i) => ({ incidentId: i.id, provider: i.provider, claimDate: i.claimDate as string, ageDays: daysBetween(i.claimDate as string, EXAMPLE_TODAY) }))
    .sort((a, b) => b.ageDays - a.ageDays);

  const incomplete = channels.reduce((total, c) => total + c.incompleteCount, 0);
  const warnings: Metrics["warnings"] = [];
  if (claimedInRange.length === 0) warnings.push({ code: "no_data", message: "No hay datos para el periodo seleccionado.", count: 0 });
  if (incomplete > 0) {
    warnings.push({
      code: "incomplete_amounts",
      message: incomplete === 1 ? "Hay 1 incidencia sin importe a reclamar: el total está incompleto." : `Hay ${incomplete} incidencias sin importe a reclamar: el total está incompleto.`,
      count: incomplete,
    });
  }

  return {
    environment,
    dateKind: kind as Metrics["dateKind"],
    criteria: { status: "example", pendingDecision: "P-04" },
    channels,
    breakdown,
    pendingClaims,
    warnings,
  };
}
