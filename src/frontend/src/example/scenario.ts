/**
 * The scenario the administrator chooses while reviewing the design: who is signed in, how slow or
 * broken the backend seems, and what data exists. It only drives the example layer.
 */
export type ScenarioRole = "administrator" | "global_manager";
export type ScenarioFailure = "none" | "network" | "server" | "storage";
export type QueueView = "running" | "completedWithErrors" | "glovoOnlyBatch";

export interface Scenario {
  role: ScenarioRole;
  /** Milliseconds each response is delayed, to see loading states. */
  latencyMs: number;
  failure: ScenarioFailure;
  /** Start with a batch already under review (UI-04, UI-12). */
  pendingBatch: boolean;
  /** Every list and the dashboard come back empty. */
  emptyData: boolean;
  /** Which example the email queue shows. */
  queueView: QueueView;
  /** A row becomes a duplicate between review and confirmation (RF-10). */
  matchesAtConfirmation: boolean;
  /** How long a batch stays in processing, in milliseconds. */
  processingMs: number;
}

export const defaultScenario: Scenario = {
  role: "administrator",
  latencyMs: 150,
  failure: "none",
  pendingBatch: false,
  emptyData: false,
  queueView: "running",
  matchesAtConfirmation: false,
  processingMs: 1500,
};

const KEY = "dh-example-scenario";
let current: Scenario = load();
const listeners = new Set<() => void>();

function load(): Scenario {
  try {
    const stored = sessionStorage.getItem(KEY);
    if (stored) return { ...defaultScenario, ...(JSON.parse(stored) as Partial<Scenario>) };
  } catch {
    // Storage can be unavailable (private window, tests); the default scenario still works.
  }
  return { ...defaultScenario };
}

export function getScenario(): Scenario {
  return current;
}

export function setScenario(patch: Partial<Scenario>): void {
  current = { ...current, ...patch };
  try {
    sessionStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    // Not persisted; the choice still applies until the page is reloaded.
  }
  listeners.forEach((listener) => listener());
}

export function resetScenario(): void {
  setScenario({ ...defaultScenario });
}

export function subscribeScenario(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
