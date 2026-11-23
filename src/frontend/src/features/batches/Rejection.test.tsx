import { screen, waitFor } from "@testing-library/react";
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
  setScenario({ latencyMs: 0, processingMs: 30 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const uploadAndWait = async (name: string) => {
  renderBatches();
  await userEvent.upload(screen.getByLabelText(es.import.fileLabel), xlsx(name));
  // Wait for the batch screen itself: the processing state can be too brief to catch.
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent(/^\/lotes\//));
};

describe("structure rejection (RF-02)", () => {
  it.each([
    ["sin-order-id.xlsx", "Falta el encabezado obligatorio «Order ID»."],
    ["dos-hojas.xlsx", "El archivo tiene más de una hoja y solo se admite una."],
    ["protegido.xlsx", "El archivo está dañado o protegido y no se puede leer."],
  ])("%s is rejected with its reason and no preview", async (file, reason) => {
    await uploadAndWait(file);
    const alert = await screen.findByRole("alert", undefined, { timeout: 4000 });
    expect(alert).toHaveTextContent(es.rejection.title);
    expect(alert).toHaveTextContent(reason);
    expect(alert).toHaveTextContent("No se ha creado ninguna incidencia");
    // No way to review or confirm a rejected file, only to try again.
    expect(screen.queryByRole("button", { name: /confirmar/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: es.import.chooseAnother })).toHaveAttribute("href", "/importar");
  });

  it("a rejected batch does not block uploading another file", async () => {
    await uploadAndWait("sin-order-id.xlsx");
    await screen.findByRole("alert", undefined, { timeout: 4000 });
    const pending = await fetch(`${location.origin}/api/batches/pending`);
    expect(pending.status).toBe(204);
  });
});

describe("identical file notice (RF-03)", () => {
  it("warns before the review and lets the administrator continue", async () => {
    await uploadAndWait("identica.xlsx");
    const alert = await screen.findByRole("alert", undefined, { timeout: 4000 });
    expect(alert).toHaveTextContent(es.identical.title);
    // 2026-11-20T12:00:00Z is 13:00 in Madrid (UTC+1 in November).
    expect(alert).toHaveTextContent("2026-11-20 13:00");
    expect(alert).toHaveTextContent("cada fila se clasifica por su propia clave");

    await userEvent.click(screen.getByRole("button", { name: es.identical.continue }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("lets the administrator cancel the batch instead", async () => {
    await uploadAndWait("identica.xlsx");
    await screen.findByRole("alert", undefined, { timeout: 4000 });
    await userEvent.click(screen.getByRole("button", { name: es.identical.cancel }));
    expect(await screen.findByRole("status")).toHaveTextContent(es.states.discardedTitle);
    expect(screen.queryByRole("button", { name: /confirmar/i })).not.toBeInTheDocument();
  });

  it("does not warn for an ordinary file", async () => {
    await uploadAndWait("incidencias.xlsx");
    await screen.findByRole("heading", { level: 2, name: es.review.temporaryTitle }, { timeout: 4000 });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
