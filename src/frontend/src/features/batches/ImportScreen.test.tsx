import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { handlers } from "../../example/handlers";
import { resetScenario, setScenario } from "../../example/scenario";
import { resetStore } from "../../example/state";
import { es } from "../../i18n/es";
import { renderBatches, xlsx } from "./testing";

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 60 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const upload = async (name?: string) =>
  userEvent.upload(screen.getByLabelText(es.import.fileLabel), xlsx(name));

describe("import screen (RF-01, RF-03)", () => {
  it("explains the input contract and shows the file limits as pending (P-06)", () => {
    renderBatches();
    expect(screen.getByRole("heading", { level: 1, name: es.titles.import })).toBeInTheDocument();
    expect(screen.getByText(es.import.requiredHeaders)).toBeInTheDocument();
    expect(screen.getByText(/Pendiente de decisión \(P-06\)/)).toBeInTheDocument();
  });

  it("uploads, requests processing and shows the batch processing", async () => {
    setScenario({ latencyMs: 250, processingMs: 5000 });
    renderBatches();
    await upload();

    // The progress is visible while the file goes to storage.
    expect(await screen.findByText(/Subiendo el archivo/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: /Subiendo el archivo/ })).toBeInTheDocument();

    // Then the user lands on the batch, which is being processed. Nothing definitive exists yet.
    expect(await screen.findByRole("heading", { level: 2, name: es.import.processingTitle })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/lotes\/lote-\d+$/);
    expect(screen.getByRole("status")).toHaveTextContent("Todavía no se ha creado ninguna incidencia");
  });

  it("moves from processing to review by itself", async () => {
    renderBatches();
    await upload();
    await screen.findByRole("heading", { level: 2, name: es.import.processingTitle });
    expect(await screen.findByRole("heading", { level: 2, name: es.review.temporaryTitle }, { timeout: 4000 })).toBeInTheDocument();
  });

  it("reports an interrupted upload and leaves no batch blocking the next one", async () => {
    setScenario({ failure: "storage" });
    renderBatches();
    await upload();

    expect(await screen.findByRole("alert")).toHaveTextContent(es.import.uploadFailed);
    expect(screen.getByTestId("where")).toHaveTextContent("/importar");

    // No batch is left under review, so the user can simply try again.
    const pending = await fetch(`${location.origin}/api/batches/pending`);
    expect(pending.status).toBe(204);
    setScenario({ failure: "none" });
    expect(screen.getByLabelText(es.import.fileLabel)).toBeEnabled();
  });

  it("says the outcome is unknown when the request that registers the batch gets no answer", async () => {
    setScenario({ failure: "network" });
    renderBatches();
    await upload();
    expect(await screen.findByRole("alert")).toHaveTextContent("no sabemos si la operación se completó");
  });
});
