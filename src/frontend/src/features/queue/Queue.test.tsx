import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import AppRoutes from "../../app/AppRoutes";
import { areas } from "../../app/areas";
import { renderAt } from "../../app/testing";
import { handlers } from "../../example/handlers";
import { resetScenario, setScenario } from "../../example/scenario";
import { resetStore } from "../../example/state";
import { es } from "../../i18n/es";

const server = setupServer(...handlers);
const t = es.queue;
const show = () => renderAt("/correo", <AppRoutes areas={areas} />);
const totals = async () => within(await screen.findByRole("region", { name: t.totalsLabel }));
const kpi = (scope: ReturnType<typeof within>, label: string) =>
  (scope.getByText(label).closest(".kpi")!.querySelector(".kpi__value") as HTMLElement).textContent;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("email queue states and totals (UI-07)", () => {
  it("shows the four states with their totals", async () => {
    show();
    const scope = await totals();
    expect(kpi(scope, t.states.pending)).toBe("1");
    expect(kpi(scope, t.states.sending)).toBe("1");
    expect(kpi(scope, t.states.sent)).toBe("1");
    expect(kpi(scope, t.states.error)).toBe("2");
  });

  it("explains each failed email and tells an unverifiable result from a failed one", async () => {
    show();
    await totals();
    expect(screen.getByText("El servidor de correo rechazó la conexión.")).toBeInTheDocument();
    expect(screen.getByText(t.errorKinds.send_failed)).toBeInTheDocument();
    expect(screen.getByText(t.errorKinds.interrupted_unverified)).toBeInTheDocument();
  });

  it("offers no retry, resend or cancel, and says why", async () => {
    show();
    await totals();
    expect(screen.queryByRole("button", { name: /reintent|reenvi|cancel/i })).not.toBeInTheDocument();
    expect(screen.getByText(t.noActions)).toBeInTheDocument();
    expect(screen.getByText(t.rules, { exact: false })).toHaveTextContent("30 segundos");
  });

  it("labels the recipient as the test recipient", async () => {
    show();
    await totals();
    expect(screen.getAllByText("Destinatario de prueba").length).toBeGreaterThan(0);
    expect(screen.getByText(t.testRecipient)).toBeInTheDocument();
  });

  it("filters the list by state without changing the totals", async () => {
    show();
    const scope = await totals();
    await userEvent.selectOptions(screen.getByLabelText(t.list.filterState), "error");
    await waitFor(() => expect(within(screen.getByRole("table", { name: t.list.label })).getAllByRole("row")).toHaveLength(3));
    expect(kpi(scope, t.states.sent)).toBe("1");
  });
});

describe("completed batches (UI-07)", () => {
  it("a completed batch with errors shows both the Sent and the Error totals", async () => {
    setScenario({ queueView: "completedWithErrors" });
    show();
    const row = (await screen.findByRole("rowheader", { name: "lote-0005" })).closest("tr")!;
    expect(within(row).getByText(t.batches.completed)).toBeInTheDocument();
    expect(within(row).getByText(t.batches.withErrors(1))).toBeInTheDocument();
    const cells = within(row).getAllByRole("cell").map((c) => c.textContent);
    expect(cells.slice(-2)).toEqual(["2", "1"]);
    expect(screen.getByText(t.batches.completedNote)).toBeInTheDocument();
  });

  it("a batch with only Glovo incidents leaves the queue empty and explains it", async () => {
    setScenario({ queueView: "glovoOnlyBatch" });
    show();
    expect(await screen.findByText(t.emptyQueue.title)).toBeInTheDocument();
    expect(screen.getByText(t.emptyQueue.text)).toBeInTheDocument();
  });
});

describe("pause and resume (UI-08)", () => {
  it("pausing shows the paused state and explains that an attempt already started may finish", async () => {
    show();
    await userEvent.click(await screen.findByRole("button", { name: t.pause }));
    expect(await screen.findByText(es.states.pausedTitle)).toBeInTheDocument();
    expect(screen.getByText(t.inFlightWhilePaused(1))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.resume })).toBeInTheDocument();
  });

  it("resuming returns to running", async () => {
    show();
    await userEvent.click(await screen.findByRole("button", { name: t.pause }));
    await userEvent.click(await screen.findByRole("button", { name: t.resume }));
    expect(await screen.findByRole("button", { name: t.pause })).toBeInTheDocument();
    expect(screen.queryByText(es.states.pausedTitle)).not.toBeInTheDocument();
  });

  it("a refused pause says nothing changed and does not claim the queue is paused", async () => {
    server.use(http.post("*/api/email-queue/pause", () => HttpResponse.json({ code: "forbidden" }, { status: 403 })));
    show();
    await userEvent.click(await screen.findByRole("button", { name: t.pause }));
    expect(await screen.findByText(es.errors.forbiddenAction)).toBeInTheDocument();
    expect(screen.queryByText(es.states.pausedTitle)).not.toBeInTheDocument();
  });

  it("a global manager has no access to the queue", async () => {
    setScenario({ role: "global_manager" });
    show();
    expect(await screen.findByText(es.states.denied)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.pause })).not.toBeInTheDocument();
  });

  it("a failed read shows an error instead of an empty queue", async () => {
    server.use(http.get("*/api/email-queue", () => HttpResponse.json({}, { status: 500 })));
    show();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
