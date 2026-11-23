import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { summaryOf } from "../../example/dataset";
import { handlers } from "../../example/handlers";
import { resetScenario, setScenario } from "../../example/scenario";
import { resetStore } from "../../example/state";
import { es } from "../../i18n/es";
import { renderBatches, xlsx } from "./testing";

const server = setupServer(...handlers);
const t = es.confirm;
const summary = summaryOf("large");

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 20 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function openPreview(file = "incidencias.xlsx") {
  renderBatches();
  await userEvent.upload(screen.getByLabelText(es.import.fileLabel), xlsx(file));
  await screen.findByRole("heading", { level: 2, name: t.title }, { timeout: 4000 });
}

const confirmButton = () => screen.getByRole("button", { name: new RegExp("^Confirmar e importar") });
const panel = () => screen.getByRole("region", { name: t.title });
const fact = (label: string) => within(panel()).getByText(label).nextElementSibling as HTMLElement;

describe("confirmation summary (RF-07, UI-03)", () => {
  it("says what will be created, to whom the emails go and with which template", async () => {
    await openPreview();
    expect(fact(t.incidents)).toHaveTextContent(String(summary.incidentsToCreate));
    expect(fact(t.emails)).toHaveTextContent(String(summary.emailsToGenerate));
    expect(fact(t.withoutEmail)).toHaveTextContent(String(summary.withoutEmail));
    expect(fact(t.excluded)).toHaveTextContent("90");
    expect(fact(t.recipient)).toHaveTextContent("Destinatario de prueba");
    expect(within(panel()).getByText("Reclamación de incidente")).toBeInTheDocument();
    expect(within(panel()).getByText(/remitimos el siguiente incidente No Incidente \{orderId\}/)).toBeInTheDocument();
  });

  it("marks the template as an example while its wording is pending (P-03)", async () => {
    await openPreview();
    expect(within(panel()).getByText(new RegExp(t.templateExample))).toBeInTheDocument();
    expect(within(panel()).getByText(/Pendiente de decisión \(P-03\)/)).toBeInTheDocument();
    expect(within(panel()).getByText(t.onlyVariable)).toBeInTheDocument();
  });

  it("warns there is no undo and no later cancellation, before the action is available", async () => {
    await openPreview();
    const notice = within(panel()).getByText(/Confirmar no se puede deshacer/);
    expect(notice).toHaveTextContent("no se pueden cancelar después");
    expect(notice).toHaveTextContent("sin reintentos");
    expect(notice.compareDocumentPosition(confirmButton()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("offers a single action, labelled with how many incidents it creates", async () => {
    await openPreview();
    expect(screen.getAllByRole("button", { name: /^Confirmar e importar/ })).toHaveLength(1);
    expect(confirmButton()).toHaveTextContent(`${summary.incidentsToCreate} incidencias`);
  });

  it("does not offer to import when there is nothing new, and says why", async () => {
    renderBatches();
    await userEvent.upload(screen.getByLabelText(es.import.fileLabel), xlsx("identica.xlsx"));
    await userEvent.click(await screen.findByRole("button", { name: es.identical.continue }, { timeout: 4000 }));
    expect(await screen.findByText(t.nothingToImport)).toBeInTheDocument();
    expect(confirmButton()).toBeDisabled();
  });
});

describe("confirming (UI-03)", () => {
  it("shows the real result and tells the temporary preparation from the definitive records", async () => {
    await openPreview();
    await userEvent.click(confirmButton());

    const done = (await screen.findByText(t.doneTitle)).closest(".notice") as HTMLElement;
    expect(done).toHaveTextContent("los correos quedan pendientes de envío");
    const card = done.nextElementSibling as HTMLElement;
    const value = (label: string) => (within(card).getByText(label).nextElementSibling as HTMLElement).textContent;
    expect(value(t.created)).toBe(String(summary.incidentsToCreate));
    expect(value(t.pendingEmails)).toBe(String(summary.emailsToGenerate));
    expect(value(t.withoutEmail)).toBe(String(summary.withoutEmail));
    expect(value(t.excluded)).toBe("90");

    // The review is over: no preview, no second confirmation.
    expect(screen.queryByRole("table", { name: es.review.tableCaption })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Confirmar e importar/ })).not.toBeInTheDocument();
    expect(screen.queryByText(es.review.temporaryTitle)).not.toBeInTheDocument();
  });

  it("lists the excluded rows with their reasons in the result", async () => {
    await openPreview();
    await userEvent.click(confirmButton());
    await screen.findByText(t.doneTitle);
    await userEvent.click(screen.getByText(t.excludedList(90)));
    expect(screen.getAllByRole("row").length).toBeGreaterThan(90);
  });

  it("with a double click, confirms once (RF-09)", async () => {
    const posts: string[] = [];
    server.events.on("request:start", ({ request }) => {
      if (request.method === "POST" && request.url.endsWith("/confirm")) posts.push(request.url);
    });
    await openPreview();
    await userEvent.dblClick(confirmButton());
    await screen.findByText(t.doneTitle);
    expect(posts).toHaveLength(1);
  });

  it("disables the control while the confirmation is in progress", async () => {
    await openPreview();
    setScenario({ latencyMs: 300 });
    const button = confirmButton();
    await userEvent.click(button);
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent(t.confirming);
    await screen.findByText(t.doneTitle);
  });

  it("reports rows that matched while reviewing: they are excluded and the rest imported (RF-10)", async () => {
    await openPreview();
    setScenario({ matchesAtConfirmation: true });
    await userEvent.click(confirmButton());
    const overtaken = await screen.findByText(t.overtakenTitle);
    expect(overtaken.closest(".notice")).toHaveTextContent("Otro lote confirmó esta incidencia");
    const card = screen.getByText(t.created).closest("dl") as HTMLElement;
    expect(within(card).getByText(t.created).nextElementSibling).toHaveTextContent(String(summary.incidentsToCreate - 1));
  });
});

describe("a confirmation that gets no answer (RF-09)", () => {
  async function pendingBatch() {
    const pending = (await (await fetch(`${location.origin}/api/batches/pending`)).json()) as { id: string; reviewedVersion: string };
    return pending;
  }

  it("never claims whether it happened, and offers to check the batch", async () => {
    await openPreview();
    setScenario({ failure: "network" });
    await userEvent.click(confirmButton());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("no sabemos si la operación se completó");
    expect(alert.textContent).not.toMatch(/no se ha (confirmado|creado|guardado)|se ha confirmado correctamente/i);
    expect(screen.getByRole("button", { name: t.checkStatus })).toBeInTheDocument();
  });

  it("checking finds the batch still in review when nothing was applied", async () => {
    await openPreview();
    setScenario({ failure: "network" });
    await userEvent.click(confirmButton());
    await screen.findByRole("alert");
    setScenario({ failure: "none" });
    await userEvent.click(screen.getByRole("button", { name: t.checkStatus }));
    expect(await screen.findByText(t.stillInReview)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Confirmar e importar/ })).toBeEnabled();
  });

  it("checking finds a batch that was confirmed and shows its stored result, creating nothing new", async () => {
    await openPreview();
    // The request reached the server but its answer was lost.
    const { id, reviewedVersion } = await pendingBatch();
    await fetch(`${location.origin}/api/batches/${id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewedVersion }),
    });
    setScenario({ failure: "network" });
    await userEvent.click(confirmButton());
    await screen.findByRole("alert");

    setScenario({ failure: "none" });
    await userEvent.click(screen.getByRole("button", { name: t.checkStatus }));
    expect(await screen.findByText(t.repeated)).toBeInTheDocument();
    expect(screen.getByText(t.doneTitle)).toBeInTheDocument();
  });
});

describe("a batch that can no longer be confirmed", () => {
  it("explains a batch discarded in the meantime, with the server's own message", async () => {
    await openPreview();
    const pending = (await (await fetch(`${location.origin}/api/batches/pending`)).json()) as { id: string };
    await fetch(`${location.origin}/api/batches/${pending.id}/discard`, { method: "POST" });
    await userEvent.click(confirmButton());
    expect(await screen.findByRole("alert")).toHaveTextContent("El lote fue descartado y ya no se puede confirmar.");
    await waitFor(() => expect(screen.queryByRole("button", { name: /^Confirmar e importar/ })).toBeInTheDocument());
  });
});
