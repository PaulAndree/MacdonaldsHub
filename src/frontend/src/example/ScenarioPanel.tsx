import { useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { exampleEs } from "./strings";
import { type Scenario, getScenario, resetScenario, setScenario, subscribeScenario } from "./scenario";
import { resetStore } from "./state";

const t = exampleEs.panel;

/** Chooses the scenario the example layer simulates. Only the example build has it. */
export default function ScenarioPanel() {
  const scenario = useSyncExternalStore(subscribeScenario, getScenario);
  const queryClient = useQueryClient();

  function change(patch: Partial<Scenario>, resetsData = false) {
    setScenario(patch);
    if (resetsData) resetStore();
    // What is on screen came from the previous scenario; ask for it again.
    void queryClient.invalidateQueries();
  }

  return (
    <details className="card">
      <summary>{t.summary}</summary>
      <div style={{ display: "grid", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
        <label>
          {t.role}{" "}
          <select value={scenario.role} onChange={(e) => change({ role: e.target.value as Scenario["role"] })}>
            <option value="administrator">{t.roleAdministrator}</option>
            <option value="global_manager">{t.roleGlobalManager}</option>
          </select>
        </label>
        <label>
          {t.latency}{" "}
          <select value={scenario.latencyMs} onChange={(e) => change({ latencyMs: Number(e.target.value) })}>
            <option value={0}>0 ms</option>
            <option value={150}>150 ms</option>
            <option value={1500}>1500 ms</option>
            <option value={4000}>4000 ms</option>
          </select>
        </label>
        <label>
          {t.failure}{" "}
          <select value={scenario.failure} onChange={(e) => change({ failure: e.target.value as Scenario["failure"] })}>
            <option value="none">{t.failureNone}</option>
            <option value="network">{t.failureNetwork}</option>
            <option value="server">{t.failureServer}</option>
            <option value="storage">{t.failureStorage}</option>
          </select>
        </label>
        <label>
          {t.queue}{" "}
          <select value={scenario.queueView} onChange={(e) => change({ queueView: e.target.value as Scenario["queueView"] })}>
            <option value="running">{t.queueRunning}</option>
            <option value="completedWithErrors">{t.queueCompleted}</option>
            <option value="glovoOnlyBatch">{t.queueGlovo}</option>
          </select>
        </label>
        <label>
          <input type="checkbox" checked={scenario.pendingBatch} onChange={(e) => change({ pendingBatch: e.target.checked }, true)} />{" "}
          {t.pendingBatch}
        </label>
        <label>
          <input type="checkbox" checked={scenario.emptyData} onChange={(e) => change({ emptyData: e.target.checked })} />{" "}
          {t.emptyData}
        </label>
        <label>
          <input
            type="checkbox"
            checked={scenario.matchesAtConfirmation}
            onChange={(e) => change({ matchesAtConfirmation: e.target.checked })}
          />{" "}
          {t.matches}
        </label>
        <div>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              resetScenario();
              resetStore();
              void queryClient.invalidateQueries();
            }}
          >
            {t.reset}
          </button>
        </div>
      </div>
    </details>
  );
}
