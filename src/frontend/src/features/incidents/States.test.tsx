import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import AppRoutes from "../../app/AppRoutes";
import { areas } from "../../app/areas";
import { renderAt } from "../../app/testing";
import { handlers } from "../../example/handlers";
import { resetScenario, setScenario } from "../../example/scenario";
import { resetStore } from "../../example/state";
import { es } from "../../i18n/es";
import EmailStateNotice from "./EmailStateNotice";
import type { HistoryEntry, Incident } from "./types";

const server = setupServer(...handlers);
const t = es.incidents;
const show = (path: string) => renderAt(path, <AppRoutes areas={areas} />);

/** Anything that would let a user try an email again. */
const RETRY = /reintent|reenv|volver a enviar|enviar de nuevo|reenviar|repetir el env/i;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("incident states (RF-21, RF-13)", () => {
  it("names every state in Spanish in the list", async () => {
    show("/incidencias");
    await screen.findByRole("table", { name: t.tableCaption });
    for (const label of [t.status.claimed, t.status.send_error, t.status.imported_no_email, t.status.resolved]) {
      expect(screen.getAllByText(label, { selector: ".pill" }).length).toBeGreaterThan(0);
    }
  });

  it("lets the incident states be filtered, including the error one", async () => {
    show("/incidencias");
    const select = await screen.findByLabelText(t.filters.status);
    const options = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual([t.filters.all, ...Object.values(t.status)]);
  });
});

describe("an email that ended in error offers no retry (UI-07, RF-13)", () => {
  it("explains the failure with its reason and says there is one attempt, with no action to try again", async () => {
    show("/incidencias/inc-002");
    const note = (await screen.findByText(t.email.errorTitle)).closest(".notice") as HTMLElement;
    expect(note).toHaveTextContent("El servidor de correo rechazó la conexión.");
    expect(note).toHaveTextContent("un solo intento");
    expect(note).toHaveTextContent("no hay reintento ni reenvío");
    expect(note).toHaveTextContent("no demuestra que el correo no llegara");

    // Nothing on the whole screen offers to try again.
    expect(screen.queryByRole("button", { name: RETRY })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: RETRY })).not.toBeInTheDocument();
    for (const button of screen.queryAllByRole("button")) expect(button.textContent).not.toMatch(RETRY);
  });

  it("shows the status as Error de envío in the header of the result", async () => {
    show("/incidencias/inc-002");
    const section = (await screen.findByRole("heading", { level: 2, name: t.sections.result })).closest("section") as HTMLElement;
    expect(within(section).getByText(t.status.send_error, { selector: ".pill" })).toBeInTheDocument();
  });

  it("says when the reason was not recorded instead of inventing one", () => {
    const incident = { status: "send_error" } as Incident;
    const history = [{ at: "2026-11-20T12:11:00Z", actor: "system", kind: "email_result", field: "status", previousValue: "pending_send", newValue: "send_error", reason: null }] as HistoryEntry[];
    render(<EmailStateNotice incident={incident} history={history} />);
    expect(screen.getByText(t.email.errorNoReason)).toBeInTheDocument();
    expect(screen.queryByText(/Motivo:/)).not.toBeInTheDocument();
  });

  it("the list has no action in any row either", async () => {
    show("/incidencias?status=send_error");
    const table = await screen.findByRole("table", { name: t.tableCaption });
    expect(within(table).queryAllByRole("button")).toHaveLength(0);
    expect(table.textContent).not.toMatch(RETRY);
  });
});

describe("an email still pending", () => {
  it("is explained, without any way to send it ahead of time", async () => {
    const call = (path: string, body?: unknown) =>
      fetch(`${location.origin}${path}`, { method: body === undefined ? "GET" : "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    const created = (await (await call("/api/batches", { fileName: "incidencias.xlsx", sizeBytes: 1 })).json()) as { batch: { id: string } };
    await call(`/api/batches/${created.batch.id}/uploaded`, {});
    const batch = (await (await call(`/api/batches/${created.batch.id}`)).json()) as { reviewedVersion: string };
    await call(`/api/batches/${created.batch.id}/confirm`, { reviewedVersion: batch.reviewedVersion });

    show("/incidencias?status=pending_send");
    const link = (await screen.findAllByRole("link", { name: /^inc-2/ }))[0]!;
    await userEvent.click(link);
    const note = (await screen.findByText(t.email.pendingTitle)).closest(".notice") as HTMLElement;
    expect(note).toHaveTextContent(t.email.pendingText);
    await waitFor(() => expect(screen.queryByRole("button", { name: RETRY })).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /enviar/i })).not.toBeInTheDocument();
  });

  it("an incident without email shows no email notice", async () => {
    show("/incidencias/inc-003");
    await screen.findByRole("heading", { level: 2, name: t.sections.history });
    expect(screen.queryByText(t.email.errorTitle)).not.toBeInTheDocument();
    expect(screen.queryByText(t.email.pendingTitle)).not.toBeInTheDocument();
  });
});
