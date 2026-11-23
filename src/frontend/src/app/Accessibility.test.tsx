import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { handlers } from "../example/handlers";
import { resetScenario, setScenario } from "../example/scenario";
import { resetStore } from "../example/state";
import { es } from "../i18n/es";
import AppRoutes from "./AppRoutes";
import { areas } from "./areas";
import { renderAt } from "./testing";

// Automated checks (RNF-08). jsdom cannot compute colors, so contrast is checked by `npm run check:contrast`.
// Keyboard use and visible focus need a person: docs/approvals/keyboard-checklist.md.
const server = setupServer(...handlers);
const options = { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } };
const api = (path: string, init?: RequestInit) => fetch(`${location.origin}${path}`, init);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0, pendingBatch: false });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function check(path: string, ready: () => Promise<unknown>) {
  const { container } = renderAt(path, <AppRoutes areas={areas} />);
  await ready();
  expect(await axe(container, options)).toHaveNoViolations();
}

describe("every area has no automated accessibility violations", () => {
  it("import", () => check("/importar", () => screen.findByLabelText(es.import.fileLabel)));
  it("incidents", () => check("/incidencias", () => screen.findAllByRole("row")));
  it("incident detail", () => check("/incidencias/inc-001", () => screen.findByRole("table")));
  it("manual entry", () => check("/incidencias/nueva", () => screen.findByRole("form").catch(() => screen.findByRole("heading", { level: 1 }))));
  it("dashboard", () => check("/panel", () => screen.findByRole("region", { name: es.metrics.channels.email })));
  it("email queue", () => check("/correo", () => screen.findByRole("region", { name: es.queue.totalsLabel })));
  it("email queue, paused", async () => {
    await check("/correo", () => screen.findByRole("button", { name: es.queue.pause }));
    await userEvent.click(screen.getByRole("button", { name: es.queue.pause }));
    await screen.findByText(es.states.pausedTitle);
  });
  it("email queue, empty (Glovo-only batch)", () => {
    setScenario({ queueView: "glovoOnlyBatch" });
    return check("/correo", () => screen.findByText(es.queue.emptyQueue.title));
  });
  it("access denied for a global manager", () => {
    setScenario({ role: "global_manager" });
    return check("/correo", () => screen.findByText(es.states.denied));
  });
  it("not found", () => check("/no-existe", () => screen.findByText(es.notFound.text)));
  it("batch review", async () => {
    const created = await api("/api/batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fileName: "incidencias.xlsx", sizeBytes: 1 }),
    });
    const id = ((await created.json()) as { batch: { id: string } }).batch.id;
    await api(`/api/batches/${id}/uploaded`, { method: "POST" });
    await check(`/lotes/${id}`, () => screen.findByRole("heading", { level: 2 }));
  });
});
