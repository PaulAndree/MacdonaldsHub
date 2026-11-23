import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { useLocation } from "react-router-dom";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import AppRoutes from "../../app/AppRoutes";
import { areas } from "../../app/areas";
import { renderAt } from "../../app/testing";
import { handlers } from "../../example/handlers";
import { resetScenario, setScenario } from "../../example/scenario";
import { resetStore } from "../../example/state";
import { es } from "../../i18n/es";

const server = setupServer(...handlers);
const t = es.incidents;

function Where() {
  const { pathname, search } = useLocation();
  return <p data-testid="where">{pathname + search}</p>;
}
const show = (path: string) =>
  renderAt(
    path,
    <>
      <AppRoutes areas={areas} />
      <Where />
    </>,
  );
const rows = () => within(screen.getByRole("table", { name: t.tableCaption })).getAllByRole("row").slice(1);
const ids = () => rows().map((row) => within(row).getAllByRole("cell")[0]!.textContent);
const waitForRows = (n: number) => waitFor(() => expect(rows()).toHaveLength(n));
const field = (label: string) => screen.getByLabelText(label);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("incident list (RF-16)", () => {
  it("lists the incidents with their status and shows absent values as such, never as zero", async () => {
    show("/incidencias");
    await screen.findByRole("table", { name: t.tableCaption });
    expect(rows()).toHaveLength(6);
    expect(screen.getByText(t.count(6))).toBeInTheDocument();

    const noBranch = rows().find((row) => row.textContent?.includes("inc-002"))!;
    expect(noBranch).toHaveTextContent(es.values.noBranch);
    expect(noBranch).toHaveTextContent(es.values.unknownAmount);
    expect(noBranch).toHaveTextContent(es.incidents.status.send_error);
    expect(noBranch).toHaveTextContent(t.noClaim);
    expect(noBranch.textContent).not.toMatch(/\b0,00|\b0 €/);
  });

  it("filters by provider and keeps the filter in the address", async () => {
    show("/incidencias");
    await waitForRows(6);
    await userEvent.selectOptions(field(t.filters.provider), "glovo");
    await waitForRows(2);
    expect(ids().sort()).toEqual(["inc-003", "inc-005"]);
    expect(screen.getByTestId("where")).toHaveTextContent("/incidencias?provider=glovo");
    expect(field(t.filters.provider)).toHaveValue("glovo");
  });

  it("filters by status and by incidents without branch", async () => {
    show("/incidencias");
    await waitForRows(6);
    await userEvent.selectOptions(field(t.filters.status), "send_error");
    await waitForRows(1);
    expect(ids()).toEqual(["inc-002"]);
    await userEvent.click(screen.getByRole("button", { name: t.filters.clear }));
    await waitForRows(6);
    await userEvent.selectOptions(field(t.filters.branch), "none");
    await waitForRows(1);
    expect(ids()).toEqual(["inc-002"]);
  });

  it("offers the real branches as options", async () => {
    show("/incidencias");
    await waitForRows(6);
    await waitFor(() => expect(within(field(t.filters.branch)).getByRole("option", { name: "centro" })).toBeInTheDocument());
    await userEvent.selectOptions(field(t.filters.branch), "norte");
    await waitForRows(2);
    expect(ids().sort()).toEqual(["inc-003", "inc-005"]);
  });

  it("filters by claim date and says which date it uses", async () => {
    show("/incidencias");
    await waitForRows(6);
    await userEvent.selectOptions(field(t.filters.dateKind), "claim");
    await userEvent.type(field(t.filters.from), "01/11/2026");
    await waitForRows(3);
    expect(ids().sort()).toEqual(["inc-001", "inc-004", "inc-006"]);
    expect(field(t.filters.dateKind)).toHaveValue("claim");
    expect(screen.getByTestId("where")).toHaveTextContent("dateKind=claim");
  });

  it("restores the filters from the address", async () => {
    show("/incidencias?provider=glovo&status=claimed");
    await screen.findByRole("heading", { level: 1, name: es.titles.incidents });
    expect(field(t.filters.provider)).toHaveValue("glovo");
    expect(field(t.filters.status)).toHaveValue("claimed");
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
  });

  it("says so when nothing matches, and the filters can be removed", async () => {
    show("/incidencias");
    await waitForRows(6);
    await userEvent.selectOptions(field(t.filters.provider), "glovo");
    await userEvent.selectOptions(field(t.filters.status), "send_error");
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t.filters.clear }));
    await waitForRows(6);
  });

  it("shows an explicit empty state when there are no incidents at all", async () => {
    setScenario({ emptyData: true });
    show("/incidencias");
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
  });

  it("pages through the incidents a confirmed batch created, stating the total", async () => {
    const call = (path: string, body?: unknown) =>
      fetch(`${location.origin}${path}`, { method: body === undefined ? "GET" : "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    const created = (await (await call("/api/batches", { fileName: "incidencias.xlsx", sizeBytes: 1 })).json()) as { batch: { id: string } };
    await call(`/api/batches/${created.batch.id}/uploaded`, {});
    const batch = (await (await call(`/api/batches/${created.batch.id}`)).json()) as { reviewedVersion: string };
    await call(`/api/batches/${created.batch.id}/confirm`, { reviewedVersion: batch.reviewedVersion });

    show("/incidencias");
    expect(await screen.findByText(t.count(416))).toBeInTheDocument();
    expect(rows()).toHaveLength(50);
    expect(screen.getByText(/Página 1 de 9/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: es.review.next }));
    await waitFor(() => expect(screen.getByText(/Filas 51 a 100 de 416/)).toBeInTheDocument());
    expect(screen.getByTestId("where")).toHaveTextContent("page=2");
  });
});

describe("incident detail and history (RF-16, RF-21)", () => {
  it("shows the incident, claim and recovery dates as three different things", async () => {
    show("/incidencias/inc-004");
    await screen.findByRole("heading", { level: 2, name: t.sections.dates });
    const dates = screen.getByRole("heading", { level: 2, name: t.sections.dates }).closest("section") as HTMLElement;
    const value = (label: string) => (within(dates).getByText(label).nextElementSibling as HTMLElement).textContent;
    expect(value(t.dates.incident)).toBe("2026-10-30");
    expect(value(t.dates.claim)).toBe("2026-11-02");
    expect(value(t.dates.recovery)).toBe("2026-11-15");
  });

  it("says plainly that a date has not happened, instead of leaving it blank or zero", async () => {
    show("/incidencias/inc-002");
    const dates = (await screen.findByRole("heading", { level: 2, name: t.sections.dates })).closest("section") as HTMLElement;
    expect(within(dates).getByText(t.noClaim)).toBeInTheDocument();
    expect(within(dates).getByText(t.noRecovery)).toBeInTheDocument();
  });

  it("shows the recovered amount explicitly next to the claimed one, without assuming it was all recovered", async () => {
    show("/incidencias/inc-004");
    const section = (await screen.findByRole("heading", { level: 2, name: t.sections.result })).closest("section") as HTMLElement;
    const value = (label: string) => (within(section).getByText(label).nextElementSibling as HTMLElement).textContent;
    expect(value(t.result.claimed)).toBe("20,00 €");
    expect(value(t.result.recovered)).toBe("12,00 €");
    expect(within(section).getByText(t.result.notePartial)).toBeInTheDocument();
  });

  it("lists the history with who, when (Madrid time), what changed and why", async () => {
    show("/incidencias/inc-005");
    const history = (await screen.findByRole("heading", { level: 2, name: t.sections.history })).closest("section") as HTMLElement;
    const table = within(history).getByRole("table");
    const body = within(table).getAllByRole("row").slice(1);
    expect(body).toHaveLength(3);
    // 2026-11-14T10:20:00Z is 11:20 in Madrid.
    const correction = body[2]!;
    expect(correction).toHaveTextContent("2026-11-14 11:20");
    expect(correction).toHaveTextContent("admin-1");
    expect(correction).toHaveTextContent(`${t.history.kinds.correction}: ${t.history.fields.recoveredAmount}`);
    expect(correction).toHaveTextContent("10,00 € → 8,00 €");
    expect(correction).toHaveTextContent("El importe recuperado era 8,00 y no 10,00.");
  });

  it("shows the system as the actor of automatic changes", async () => {
    show("/incidencias/inc-001");
    const history = (await screen.findByRole("heading", { level: 2, name: t.sections.history })).closest("section") as HTMLElement;
    expect(within(history).getAllByText(t.history.system).length).toBeGreaterThan(0);
  });

  it("links the incident to its batch, or says it was a manual entry", async () => {
    show("/incidencias/inc-001");
    expect(await screen.findByRole("link", { name: "lote-0005" })).toHaveAttribute("href", "/lotes/lote-0005");
  });

  it("explains an incident that does not exist", async () => {
    show("/incidencias/inc-999");
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.notFound);
  });

  it("opens the incident from the list", async () => {
    show("/incidencias");
    await waitForRows(6);
    await userEvent.click(screen.getByRole("link", { name: "inc-004" }));
    expect(await screen.findByRole("heading", { level: 1, name: t.detailTitle("UE-097500") })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t.back })).toHaveAttribute("href", "/incidencias");
  });
});

describe("a global manager only consults", () => {
  it("lists incidents but is not offered to create one", async () => {
    setScenario({ role: "global_manager" });
    show("/incidencias");
    await waitForRows(6);
    expect(screen.queryByRole("link", { name: t.newEntry })).not.toBeInTheDocument();
  });
});

describe("date filters are typed as dd/mm/aaaa", () => {
  it("uses text boxes with the Spanish format", async () => {
    show("/incidencias");
    await waitForRows(6);
    expect(field(t.filters.from)).toHaveAttribute("type", "text");
    expect(field(t.filters.from)).toHaveAttribute("placeholder", "dd/mm/aaaa");
    expect(document.querySelector('input[type="date"]')).toBeNull();
  });

  it("shows the date from the address in the Spanish format", async () => {
    show("/incidencias?dateKind=claim&from=2026-11-01&to=2026-11-30");
    await screen.findByRole("heading", { level: 1, name: es.titles.incidents });
    expect(field(t.filters.from)).toHaveValue("01/11/2026");
    expect(field(t.filters.to)).toHaveValue("30/11/2026");
  });

  it("keeps the ISO date in the address and filters by it", async () => {
    show("/incidencias");
    await waitForRows(6);
    await userEvent.selectOptions(field(t.filters.dateKind), "claim");
    await userEvent.type(field(t.filters.from), "01/11/2026");
    await waitForRows(3);
    expect(screen.getByTestId("where")).toHaveTextContent("from=2026-11-01");
  });

  it("does not change the filter while the text is not a real date, and says so", async () => {
    show("/incidencias");
    await waitForRows(6);
    await userEvent.type(field(t.filters.from), "31/02/2026");
    expect(await screen.findByText(es.dates.invalid)).toBeInTheDocument();
    expect(screen.getByTestId("where")).not.toHaveTextContent("from=");
    expect(rows()).toHaveLength(6);
  });

  it("shows the typed date again after the filters are cleared", async () => {
    show("/incidencias?from=2026-11-01");
    await waitForRows(4);
    await userEvent.click(screen.getByRole("button", { name: t.filters.clear }));
    await waitForRows(6);
    expect(field(t.filters.from)).toHaveValue("");
  });
});
