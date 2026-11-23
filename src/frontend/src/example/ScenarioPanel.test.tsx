import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createQueryClient } from "../api/queryClient";
import ScenarioPanel from "./ScenarioPanel";
import { defaultScenario, getScenario, resetScenario } from "./scenario";
import { pendingRecord, resetStore } from "./state";
import { exampleEs } from "./strings";

function renderPanel() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <ScenarioPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  resetScenario();
  resetStore();
});
afterEach(() => {
  resetScenario();
  resetStore();
});

describe("scenario panel", () => {
  it("changes the scenario and can restore the default", async () => {
    renderPanel();
    await userEvent.click(screen.getByText(exampleEs.panel.summary));
    await userEvent.selectOptions(screen.getByLabelText(exampleEs.panel.role), "global_manager");
    await userEvent.selectOptions(screen.getByLabelText(exampleEs.panel.failure), "server");
    await userEvent.click(screen.getByLabelText(exampleEs.panel.emptyData));
    expect(getScenario()).toMatchObject({ role: "global_manager", failure: "server", emptyData: true });
    await userEvent.click(screen.getByRole("button", { name: exampleEs.panel.reset }));
    expect(getScenario()).toEqual(defaultScenario);
  });

  it("starting with a batch under review seeds one, and clearing it removes it", async () => {
    renderPanel();
    await userEvent.click(screen.getByText(exampleEs.panel.summary));
    await userEvent.click(screen.getByLabelText(exampleEs.panel.pendingBatch));
    expect(pendingRecord()).toBeDefined();
    await userEvent.click(screen.getByLabelText(exampleEs.panel.pendingBatch));
    expect(pendingRecord()).toBeUndefined();
  });
});
