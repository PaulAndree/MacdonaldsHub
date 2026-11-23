import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { createQueryClient } from "../api/queryClient";
import { es } from "../i18n/es";
import { handlers } from "../example/handlers";
import { resetScenario, setScenario } from "../example/scenario";
import { resetStore } from "../example/state";
import { ErrorState } from "./StateViews";
import { useAction } from "./useAction";

/** An administrative action as an area screen will build it: a button, an action and its error. */
function PauseButton({ onDone }: { onDone?: () => void }) {
  const pause = useAction(() => api.post("/api/email-queue/pause"));
  return (
    <>
      <button type="button" disabled={pause.pending} onClick={() => pause.run(undefined, { onSuccess: onDone })}>
        Pausar la cola
      </button>
      {pause.error != null && <ErrorState mutation error={pause.error} />}
      {pause.succeeded && <p role="status">Cola en pausa</p>}
    </>
  );
}

const server = setupServer(...handlers);
const url = (path: string) => `${location.origin}${path}`;

function renderWithClient(ui: React.ReactElement) {
  const client = createQueryClient({ retryDelay: 0 });
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) };
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("a denied administrative action (UI-10)", () => {
  it("shows the denial from the API and changes nothing", async () => {
    setScenario({ role: "global_manager" });
    renderWithClient(<PauseButton />);
    await userEvent.click(screen.getByRole("button", { name: "Pausar la cola" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.forbiddenAction);
    expect(screen.getByRole("alert")).toHaveTextContent("No se ha realizado ningún cambio");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    // Nothing changed on the server: as an administrator, the queue is still running.
    setScenario({ role: "administrator" });
    const queue = (await (await fetch(url("/api/email-queue"))).json()) as { status: { paused: boolean } };
    expect(queue.status.paused).toBe(false);
  });

  it("lets the same action succeed for an administrator", async () => {
    renderWithClient(<PauseButton />);
    await userEvent.click(screen.getByRole("button", { name: "Pausar la cola" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Cola en pausa");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("refreshes the session after a refusal, because the role may have changed", async () => {
    setScenario({ role: "global_manager" });
    const { client } = renderWithClient(<PauseButton />);
    const spy = vi.spyOn(client, "invalidateQueries");
    await userEvent.click(screen.getByRole("button", { name: "Pausar la cola" }));
    await screen.findByRole("alert");
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ queryKey: ["session"] }));
  });

  it("disables the control while the action runs, so it cannot be repeated", async () => {
    setScenario({ latencyMs: 300 });
    renderWithClient(<PauseButton />);
    const button = screen.getByRole("button", { name: "Pausar la cola" });
    await userEvent.click(button);
    expect(button).toBeDisabled();
    await screen.findByRole("status");
    expect(button).toBeEnabled();
  });
});

describe("other failures of an action are never silent either", () => {
  it("says the outcome is unknown after a network failure", async () => {
    setScenario({ failure: "network" });
    renderWithClient(<PauseButton />);
    await userEvent.click(screen.getByRole("button", { name: "Pausar la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no sabemos si la operación se completó");
  });

  it("shows a server error without claiming an outcome", async () => {
    setScenario({ failure: "server" });
    renderWithClient(<PauseButton />);
    await userEvent.click(screen.getByRole("button", { name: "Pausar la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.generic);
  });
});
