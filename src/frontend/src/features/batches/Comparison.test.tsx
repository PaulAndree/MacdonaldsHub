import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { datasetOf } from "../../example/dataset";
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
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

async function openPreview(file = "incidencias.xlsx") {
  renderBatches();
  await userEvent.upload(screen.getByLabelText(es.import.fileLabel), xlsx(file));
  await screen.findByRole("heading", { level: 2, name: es.review.temporaryTitle }, { timeout: 4000 });
  await screen.findByRole("table");
}

const classButton = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name}`) });
const rowOf = (n: number) => within(screen.getByRole("table")).getByText(String(n), { selector: "td" }).closest("tr") as HTMLElement;

describe("conflict with an existing incident: both versions (RF-04)", () => {
  it("shows the file version next to the existing one with the differing fields marked", async () => {
    const conflict = datasetOf("large").rows.find((r) => r.class === "conflict" && r.comparison?.differingFields.includes("claimAmount"))!;
    await openPreview();
    await userEvent.click(classButton("En conflicto"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 18"));

    await userEvent.click(within(rowOf(conflict.rowNumber)).getByRole("button", { name: new RegExp(es.review.detail) }));
    const heading = await screen.findByRole("heading", { level: 3, name: es.review.compare.title });
    const table = heading.parentElement!.querySelector("table") as HTMLElement;

    const columns = within(table).getAllByRole("columnheader").map((c) => c.textContent);
    expect(columns).toEqual([es.review.compare.field, es.review.compare.file, es.review.compare.existing]);

    // The amount differs: both values are there, and only that row is flagged.
    const amountRow = within(table).getByRole("rowheader", { name: es.review.compare.fields.claimAmount }).closest("tr") as HTMLElement;
    expect(amountRow).toHaveClass("diff");
    expect(amountRow).toHaveTextContent(es.review.compare.differs);
    const cells = within(amountRow).getAllByRole("cell");
    expect(cells[0]!.textContent).not.toBe(cells[1]!.textContent?.replace(` · ${es.review.compare.differs}`, ""));
    const orderRow = within(table).getByRole("rowheader", { name: es.review.compare.fields.orderId }).closest("tr") as HTMLElement;
    expect(orderRow).not.toHaveClass("diff");
  });

  it("marks several differing fields at once", async () => {
    const conflict = datasetOf("large").rows.find((r) => r.comparison?.differingFields.length === 2)!;
    await openPreview();
    await userEvent.click(classButton("En conflicto"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 18"));
    await userEvent.click(within(rowOf(conflict.rowNumber)).getByRole("button", { name: new RegExp(es.review.detail) }));
    const table = (await screen.findByRole("heading", { level: 3, name: es.review.compare.title })).parentElement!.querySelector("table") as HTMLElement;
    expect(within(table).getAllByText(new RegExp(es.review.compare.differs))).toHaveLength(2);
  });

  it("opens and closes the detail, and tells assistive technology which state it is in", async () => {
    const conflict = datasetOf("large").rows.find((r) => r.comparison)!;
    await openPreview();
    await userEvent.click(classButton("En conflicto"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 18"));
    const button = within(rowOf(conflict.rowNumber)).getByRole("button", { name: new RegExp(es.review.detail) });
    expect(button).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(button);
    expect(screen.queryByRole("heading", { level: 3, name: es.review.compare.title })).not.toBeInTheDocument();
  });
});

describe("keys repeated inside the file (RF-04)", () => {
  it("lists every other occurrence, and says none of them is imported", async () => {
    const repeated = datasetOf("large").rows.find((r) => r.class === "duplicate" && r.repeatedInFile.length > 0)!;
    await openPreview();
    await userEvent.click(classButton("Duplicadas"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 60"));
    await userEvent.click(within(rowOf(repeated.rowNumber)).getByRole("button", { name: new RegExp(es.review.detail) }));
    expect(await screen.findByRole("heading", { level: 3, name: es.review.repeated.title })).toBeInTheDocument();
    expect(screen.getByText(es.review.repeated.text(repeated.repeatedInFile))).toBeInTheDocument();
  });

  it("offers a detail only for rows that have something more to show", async () => {
    await openPreview();
    await userEvent.click(classButton("Con error"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("de 12"));
    expect(screen.queryAllByRole("button", { name: new RegExp(es.review.detail) })).toHaveLength(0);
  });
});

describe("report of the excluded rows (RF-20)", () => {
  function captureDownload() {
    const created: Blob[] = [];
    const names: string[] = [];
    URL.createObjectURL = vi.fn((blob: Blob | MediaSource) => {
      created.push(blob as Blob);
      return "blob:report";
    });
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
    return { created, names };
  }

  it("downloads a spreadsheet with the excluded rows and their reasons", async () => {
    const { created, names } = captureDownload();
    await openPreview();
    expect(screen.getByText(es.review.report.help)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: es.review.report.button }));
    await waitFor(() => expect(created).toHaveLength(1));
    expect(created[0]!.type).toContain("spreadsheetml");
    expect(created[0]!.size).toBeGreaterThan(500);
    expect(names[0]).toMatch(/\.xlsx$/);
  });

  it("is not offered when no row is excluded", async () => {
    await openPreview("solo-obligatorios.xlsx");
    expect(screen.getByText("No hay filas excluidas.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: es.review.report.button })).not.toBeInTheDocument();
  });

  it("reports a failed download instead of failing silently", async () => {
    captureDownload();
    server.use(http.get("*/api/batches/:id/excluded-report", () => HttpResponse.json({ code: "x", message: "x" }, { status: 500 })));
    await openPreview();
    await userEvent.click(screen.getByRole("button", { name: es.review.report.button }));
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.generic);
  });
});
