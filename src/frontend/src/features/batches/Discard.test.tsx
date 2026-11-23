import { screen, waitFor, within } from "@testing-library/react";
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
import { xlsx } from "./testing";

const server = setupServer(...handlers);
const show = (path: string) => renderAt(path, <AppRoutes areas={areas} />);
const api = (path: string, init?: RequestInit) => fetch(`${location.origin}${path}`, init);
const pendingStatus = async () => (await api("/api/batches/pending")).status;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 20, pendingBatch: true });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const t = es.pending;
const logout = es.logout;
const logoutButton = () => screen.findByRole("button", { name: logout.button });

describe("cancel before confirming (UI-04, RF-17)", () => {
  it("asks first, then discards: the batch can no longer be confirmed", async () => {
    show("/lotes/lote-0006");
    await userEvent.click(await screen.findByRole("button", { name: t.cancel }));
    const ask = screen.getByRole("group", { name: t.askTitle });
    expect(ask).toHaveTextContent("ya no se podrá confirmar");

    await userEvent.click(within(ask).getByRole("button", { name: t.askYes }));
    expect(await screen.findByText(es.states.discardedTitle)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Confirmar e importar/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.cancel })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: es.import.chooseAnother })).toBeInTheDocument();
    expect(await pendingStatus()).toBe(204);
  });

  it("keeps the batch when the administrator changes their mind", async () => {
    show("/lotes/lote-0006");
    await userEvent.click(await screen.findByRole("button", { name: t.cancel }));
    await userEvent.click(screen.getByRole("button", { name: t.askNo }));
    expect(screen.getByRole("button", { name: t.cancel })).toBeInTheDocument();
    expect(await pendingStatus()).toBe(200);
  });

  it("is not offered once the batch is confirmed", async () => {
    show("/lotes/lote-0005");
    await screen.findByText(es.confirm.confirmedOn);
    expect(screen.queryByRole("button", { name: t.cancel })).not.toBeInTheDocument();
  });

  it("says so when cancelling fails, and leaves the batch as it was", async () => {
    show("/lotes/lote-0006");
    await userEvent.click(await screen.findByRole("button", { name: t.cancel }));
    setScenario({ failure: "server" });
    await userEvent.click(screen.getByRole("button", { name: t.askYes }));
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.generic);
    setScenario({ failure: "none" });
    expect(await pendingStatus()).toBe(200);
  });
});

describe("Cerrar sesión (UI-04, RF-17)", () => {
  it("asks first and says what will be discarded and that Google stays signed in", async () => {
    show("/panel");
    await userEvent.click(await logoutButton());
    const dialog = await screen.findByRole("alertdialog", { name: logout.title });
    expect(dialog).toHaveTextContent("incidencias-octubre.xlsx");
    expect(dialog).toHaveTextContent(/se descartará/i);
    expect(dialog).toHaveTextContent("no cierra su sesión de Google");
    expect(await pendingStatus()).toBe(200);
  });

  it("discards the unconfirmed batches and keeps the Google session open", async () => {
    show("/panel");
    await userEvent.click(await logoutButton());
    await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: logout.confirm }));

    const status = await screen.findByText(/Se ha descartado 1 lote sin confirmar/);
    expect(status).toHaveTextContent(logout.googleOpen);
    expect(await pendingStatus()).toBe(204);
    // Still signed in: the session is still there and nothing asks to sign in again.
    expect(screen.getByText("administrador@example.test")).toBeInTheDocument();
    expect(screen.queryByText(es.access.noSessionTitle)).not.toBeInTheDocument();
    // The discarded batch can no longer be confirmed.
    expect(((await (await api("/api/batches/lote-0006")).json()) as { state: string }).state).toBe("discarded");
  });

  it("does not discard anything if the administrator goes back", async () => {
    show("/panel");
    await userEvent.click(await logoutButton());
    await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: logout.keep }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(await pendingStatus()).toBe(200);
  });

  it("with no unconfirmed batch it does not ask, and still touches nothing else", async () => {
    setScenario({ pendingBatch: false });
    resetStore();
    show("/panel");
    await userEvent.click(await logoutButton());
    expect(await screen.findByText(new RegExp(logout.done(0)))).toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByText("administrador@example.test")).toBeInTheDocument();
  });

  it("says so when the discard fails, and the batch stays as it was", async () => {
    show("/panel");
    await userEvent.click(await logoutButton());
    const dialog = await screen.findByRole("alertdialog");
    setScenario({ failure: "server" });
    await userEvent.click(within(dialog).getByRole("button", { name: logout.confirm }));
    expect(await within(dialog).findByText(logout.failed)).toBeInTheDocument();
    setScenario({ failure: "none" });
    expect(await pendingStatus()).toBe(200);
  });
});

describe("a batch waiting when the user returns (RF-17)", () => {
  it("is offered back on any screen with the three actions, and it does not expire", async () => {
    show("/incidencias");
    const notice = await screen.findByRole("region", { name: t.title });
    expect(notice).toHaveTextContent("incidencias-octubre.xlsx");
    expect(notice).toHaveTextContent("no caduca");
    expect(within(notice).getByRole("link", { name: t.resume })).toHaveAttribute("href", "/lotes/lote-0006");
    expect(within(notice).getByRole("link", { name: t.confirmNow })).toHaveAttribute("href", "/lotes/lote-0006#confirmacion");
    expect(within(notice).getByRole("button", { name: t.cancel })).toBeInTheDocument();
    // No countdown or deadline anywhere.
    expect(document.body.textContent).not.toMatch(/caduca (en|a las)|quedan \d+ min|expira/i);
  });

  it("can be cancelled from the notice", async () => {
    show("/incidencias");
    const notice = await screen.findByRole("region", { name: t.title });
    await userEvent.click(within(notice).getByRole("button", { name: t.cancel }));
    await userEvent.click(within(notice).getByRole("button", { name: t.askYes }));
    await waitFor(() => expect(screen.queryByRole("region", { name: t.title })).not.toBeInTheDocument());
    expect(await pendingStatus()).toBe(204);
  });

  it("is not shown when there is no unconfirmed batch", async () => {
    setScenario({ pendingBatch: false });
    resetStore();
    show("/incidencias");
    await screen.findByRole("heading", { level: 1, name: es.titles.incidents });
    expect(screen.queryByRole("region", { name: t.title })).not.toBeInTheDocument();
  });
});

describe("one unconfirmed batch per user (UI-12)", () => {
  it("blocks a new upload, names the pending batch and offers to resume or cancel it", async () => {
    show("/importar");
    const notice = await screen.findByRole("region", { name: t.blockedTitle });
    expect(notice).toHaveTextContent("incidencias-octubre.xlsx");
    expect(notice).toHaveTextContent("Solo puede tener un lote sin confirmar");
    expect(within(notice).getByRole("link", { name: t.resume })).toHaveAttribute("href", "/lotes/lote-0006");
    expect(within(notice).getByRole("button", { name: t.cancel })).toBeInTheDocument();
    expect(screen.getByLabelText(es.import.fileLabel)).toBeDisabled();
  });

  it("allows uploading again once the pending batch is cancelled", async () => {
    show("/importar");
    const notice = await screen.findByRole("region", { name: t.blockedTitle });
    await userEvent.click(within(notice).getByRole("button", { name: t.cancel }));
    await userEvent.click(within(notice).getByRole("button", { name: t.askYes }));
    await waitFor(() => expect(screen.getByLabelText(es.import.fileLabel)).toBeEnabled());
    expect(screen.queryByRole("region", { name: t.blockedTitle })).not.toBeInTheDocument();
  });

  it("a rejected batch does not block a new upload", async () => {
    setScenario({ pendingBatch: false });
    resetStore();
    show("/importar");
    await userEvent.upload(await screen.findByLabelText(es.import.fileLabel), xlsx("sin-order-id.xlsx"));
    await screen.findByRole("alert", undefined, { timeout: 4000 });
    await userEvent.click(screen.getByRole("link", { name: es.import.chooseAnother }));
    expect(await screen.findByLabelText(es.import.fileLabel)).toBeEnabled();
    expect(screen.queryByRole("region", { name: t.blockedTitle })).not.toBeInTheDocument();
  });

  it("explains the refusal when another batch appeared in the meantime, and then blocks", async () => {
    setScenario({ pendingBatch: false });
    resetStore();
    show("/importar");
    const input = await screen.findByLabelText(es.import.fileLabel);
    // Another window creates a batch after this screen loaded.
    await api("/api/batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fileName: "otra-ventana.xlsx", sizeBytes: 1 }),
    });
    await userEvent.upload(input, xlsx("incidencias.xlsx"));
    expect(await screen.findByText(/Ya tiene un lote sin confirmar/)).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: t.blockedTitle })).toHaveTextContent("otra-ventana.xlsx");
  });
});
