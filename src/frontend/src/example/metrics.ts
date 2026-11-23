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

/** What PostgreSQL aggregates in the real backend, worked out here the same way (P-04). */
function figures(group: Incident[]) {
  const claims = group.filter((i) => i.claimDate !== null);
  const recoveries = group.filter((i) => i.status === "resolved");
  const claimedAmounts = claims.map((i) => i.claimAmount).filter((v): v is string => v !== null);
  const recoveredAmounts = recoveries.map((i) => i.recoveredAmount).filter((v): v is string => v !== null);
  return {
    claimedCount: claims.length,
    claimedAmount: sumDecimals(claimedAmounts),
    recoveredCount: recoveries.length,
    recoveredAmount: sumDecimals(recoveredAmounts),
    incompleteCount: claims.length - claimedAmounts.length,
  };
}

/** Incidents with a missing amount of either kind (claim or recovered), for the warning. */
function withMissingAmount(group: Incident[]): number {
  return new Set([
    ...group.filter((i) => i.claimDate !== null && i.claimAmount === null).map((i) => i.id),
    ...group.filter((i) => i.status === "resolved" && i.recoveredAmount === null).map((i) => i.id),
  ]).size;
}

/** Recoveries over claims, by number, with four decimals. Not calculable without claims or by recovery date. */
function recoveryRate(recovered: number, claimed: number, dateKind: string): string | null {
  return claimed === 0 || dateKind === "recovery" ? null : ratio(String(recovered), String(claimed));
}

/**
 * The dashboard of the example, with the criteria the administrator decided (P-04): a claim is an
 * incident with a claim date, a recovery is a Resuelta incident, the rate is recoveries over claims
 * by number, amounts add up what is known and count what is missing (never as zero), and the age is
 * in calendar days. This imitates the backend, which does the same sums in PostgreSQL.
 */
export function computeMetrics(store: IncidentStore, query: MetricsQuery, environment: Environment): Metrics {
  const kind = query.dateKind || "claim";
  const scope = store.items
    .filter((i) => !query.provider || i.provider === query.provider)
    .filter((i) => !query.branch || (query.branch === "none" ? i.branch === null : i.branch === query.branch))
    .filter((i) => {
      if (!query.from && !query.to) return true;
      const date = dateOf(i, kind);
      return date !== null && (!query.from || date >= query.from) && (!query.to || date <= query.to);
    });

  if (scope.length === 0) {
    return {
      environment,
      dateKind: kind as Metrics["dateKind"],
      criteria: { status: "approved", pendingDecision: null },
      channels: [],
      breakdown: [],
      pendingClaims: [],
      warnings: [{ code: "no_data", message: "No hay datos para el periodo seleccionado.", count: 0 }],
    };
  }

  const channels = (["email", "glovo"] as const).map((channel) => {
    const f = figures(scope.filter((i) => i.channel === channel));
    return { channel, ...f, recoveryRate: recoveryRate(f.recoveredCount, f.claimedCount, kind) };
  });

  const keys = [...new Set(scope.map((i) => `${i.provider}|${i.branch ?? ""}`))].sort();
  const breakdown = keys
    .map((key) => {
      const [provider, branch] = key.split("|") as [Incident["provider"], string];
      const group = scope.filter((i) => i.provider === provider && (i.branch ?? "") === branch);
      const f = figures(group);
      return { provider, branch: branch === "" ? null : branch, ...f };
    })
    .filter((row) => row.claimedCount > 0 || row.recoveredCount > 0);

  const pendingClaims = scope
    .filter((i) => i.status === "claimed" && i.claimDate !== null)
    .map((i) => ({ incidentId: i.id, provider: i.provider, claimDate: i.claimDate as string, ageDays: Math.max(0, daysBetween(i.claimDate as string, EXAMPLE_TODAY)) }))
    .sort((a, b) => b.ageDays - a.ageDays);

  const incomplete = withMissingAmount(scope);
  const warnings: Metrics["warnings"] = [];
  if (incomplete > 0) {
    warnings.push({
      code: "incomplete_amounts",
      message: `Hay ${incomplete} ${incomplete === 1 ? "incidencia sin importe" : "incidencias sin importe"}: los totales están incompletos.`,
      count: incomplete,
    });
  }

  return {
    environment,
    dateKind: kind as Metrics["dateKind"],
    criteria: { status: "approved", pendingDecision: null },
    channels,
    breakdown,
    pendingClaims,
    warnings,
  };
}
