import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
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
  setScenario({ latencyMs: 0, processingMs: 20 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function openPreview(file = "incidencias.xlsx") {
  renderBatches();
  await userEvent.upload(screen.getByLabelText(es.import.fileLabel), xlsx(file));
  await screen.findByRole("heading", { level: 2, name: es.review.temporaryTitle }, { timeout: 4000 });
  await screen.findByRole("table");
}

const classButton = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name}`) });
const bodyRows = () => within(screen.getByRole("table")).getAllByRole("row").slice(1);

describe("preview of a prepared batch (UI-02, RF-04 to RF-06)", () => {
  it("says it is a temporary preparation and that nothing exists yet", async () => {
    await openPreview();
    expect(screen.getByRole("heading", { level: 2, name: es.review.temporaryTitle })).toBeInTheDocument();
    expect(screen.getByText(/Todavía no existe ninguna incidencia ni ningún correo de este lote/)).toBeInTheDocument();
  });

  it("shows the count of every class and what will and will not be imported", async () => {
    await openPreview();
    expect(classButton("Todas")).toHaveTextContent("500");
    expect(classButton("Nuevas")).toHaveTextContent("410");
    expect(classButton("Duplicadas")).toHaveTextContent("60");
    expect(classButton("En conflicto")).toHaveTextContent("18");
    expect(classButton("Con error")).toHaveTextContent("12");
    expect(screen.getByText("Se importarán 410 incidencias nuevas.")).toBeInTheDocument();
    expect(screen.getByText(/Se excluyen 90 filas/)).toBeInTheDocument();
  });

  it("pages through all 500 rows without truncating, saying how many there are", async () => {
    await openPreview();
    expect(bodyRows()).toHaveLength(50);
    expect(screen.getByRole("status")).toHaveTextContent("Filas 1 a 50 de 500 · Página 1 de 10");
    expect(screen.getByRole("button", { name: es.review.previous })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: es.review.next }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Filas 51 a 100 de 500 · Página 2 de 10"));
    // Row 1 of the file is the header, so the 51st listed row is row 52.
    expect(bodyRows()[0]).toHaveTextContent(/^52/);
    expect(screen.getByRole("button", { name: es.review.previous })).toBeEnabled();
  });

  it("filters by class, keeps every total visible and returns to the first page", async () => {
    await openPreview();
    await userEvent.click(screen.getByRole("button", { name: es.review.next }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Página 2"));

    await userEvent.click(classButton("Con error"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Filas 1 a 12 de 12 · Página 1 de 1"));
    expect(bodyRows()).toHaveLength(12);
    expect(classButton("Con error")).toHaveAttribute("aria-pressed", "true");
    // The other counts are still there.
    expect(classButton("Nuevas")).toHaveTextContent("410");
    expect(classButton("Todas")).toHaveTextContent("500");
  });

  it("explains why every excluded row is excluded, and shows no reason for a new row", async () => {
    await openPreview();
    await userEvent.click(classButton("Con error"));
    await waitFor(() => expect(bodyRows()).toHaveLength(12));
    for (const row of bodyRows()) {
      expect(within(row).getByText("Con error", { selector: ".pill" })).toBeInTheDocument();
      const reason = within(row).getAllByRole("cell")[7]!;
      expect(reason.textContent?.length).toBeGreaterThan(10);
    }
    expect(screen.getAllByText(/La fecha 12\/11\/2026 no tiene el formato YYYY-MM-DD/).length).toBeGreaterThan(0);

    await userEvent.click(classButton("Nuevas"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 410"));
    for (const row of bodyRows().slice(0, 10)) {
      expect(within(row).getAllByRole("cell")[7]).toHaveTextContent(/^$/);
    }
  });

  it("shows every excluded kind: duplicates, conflicts and errors, each with its own reason", async () => {
    await openPreview();
    await userEvent.click(classButton("Duplicadas"));
    await waitFor(() => expect(bodyRows()).toHaveLength(50));
    expect(screen.getAllByText(/misma clave y los mismos datos/).length + screen.queryAllByText(/repetida en el archivo/).length).toBeGreaterThan(0);
    await userEvent.click(classButton("En conflicto"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 18"));
    expect(screen.getAllByText(/datos distintos/).length).toBeGreaterThan(0);
  });
});

describe("the browser never recomputes a class", () => {
  it("shows the class the backend supplied even when the content seems to say otherwise", async () => {
    server.use(
      http.get("*/api/batches/:id/rows", () =>
        HttpResponse.json({
          page: 1,
          pageSize: 50,
          total: 2,
          totalsByClass: { new: 1, duplicate: 0, conflict: 0, error: 1 },
          items: [
            // A row that looks invalid, but the backend called it new.
            { rowNumber: 2, class: "new", reason: null, comparison: null, repeatedInFile: [], fields: { provider: "ubereats", orderId: null, incidentDate: "12/11/2026", incidentTime: null, branch: "desconocida", claimAmount: "12,50 €", providerCosts: null, total: null, description: null } },
            // A row that looks perfect, but the backend called it an error.
            { rowNumber: 3, class: "error", reason: "Motivo decidido por el backend.", comparison: null, repeatedInFile: [], fields: { provider: "uber eats", orderId: "UE-1", incidentDate: "2026-11-18", incidentTime: null, branch: "centro", claimAmount: "10.00", providerCosts: null, total: null, description: null } },
          ],
        }),
      ),
    );
    await openPreview();
    const [first, second] = bodyRows();
    expect(within(first!).getByText("Nueva", { selector: ".pill" })).toBeInTheDocument();
    expect(within(second!).getByText("Con error", { selector: ".pill" })).toBeInTheDocument();
    expect(within(second!).getByText("Motivo decidido por el backend.")).toBeInTheDocument();
  });
});

describe("a file with only the three required columns (UI-01)", () => {
  it("is a valid preview with optional values shown as unknown, never as zero", async () => {
    await openPreview("solo-obligatorios.xlsx");
    expect(screen.getByText("Se importarán 6 incidencias nuevas.")).toBeInTheDocument();
    const rows = bodyRows();
    expect(rows).toHaveLength(6);
    for (const row of rows) {
      expect(within(row).getByText(es.values.noBranch)).toBeInTheDocument();
      expect(within(row).getByText(es.values.unknownAmount)).toBeInTheDocument();
      expect(row.textContent).not.toMatch(/0,00|\b0 €/);
    }
  });
});

describe("values are shown as they came (RNF-13)", () => {
  it("keeps amounts with more than two decimals and the time only when it exists", async () => {
    await openPreview();
    await userEvent.click(classButton("Nuevas"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 410"));
    const text = screen.getByRole("table").textContent ?? "";
    expect(text).toMatch(/\d,\d{4} €/);
    expect(text).not.toContain("00:00");
  });
});
