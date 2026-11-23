/* eslint-disable @typescript-eslint/no-explicit-any -- responses are inspected loosely in these tests */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { useLocation } from "react-router-dom";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import AppRoutes from "../../app/AppRoutes";
import { areas } from "../../app/areas";
import { renderAt } from "../../app/testing";
import { handlers } from "../../example/handlers";
import { seedIncidents } from "../../example/incidents";
import { computeMetrics } from "../../example/metrics";
import { resetScenario, setScenario } from "../../example/scenario";
import { resetStore } from "../../example/state";
import { es } from "../../i18n/es";

const server = setupServer(...handlers);
const t = es.metrics;

function Where() {
  const { pathname, search } = useLocation();
  return <p data-testid="where">{pathname + search}</p>;
}
const show = (path = "/panel") =>
  renderAt(
    path,
    <>
      <AppRoutes areas={areas} />
      <Where />
    </>,
  );
const api = async (path: string, body?: unknown) =>
  (await fetch(`${location.origin}${path}`, { method: body === undefined ? "GET" : "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json() as Promise<any>;

const channel = async (name: string) => (await screen.findByRole("region", { name })) as HTMLElement;
const kpi = (section: HTMLElement, label: string) => {
  const card = within(section).getByText(label).closest(".kpi") as HTMLElement;
  return (card.querySelector(".kpi__value") as HTMLElement).textContent;
};
const field = (label: string) => screen.getByLabelText(label);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resetScenario();
  setScenario({ latencyMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("dashboard in the test environment (UI-06, RF-15, RF-12)", () => {
  it("identifies the environment and says its figures are not real production activity", async () => {
    show();
    expect(await screen.findByText(t.subtitle("Pruebas"))).toBeInTheDocument();
    expect(screen.getByText(t.envTest)).toBeInTheDocument();
  });

  it("does not present test figures as production, and says so for production", async () => {
    server.use(http.get("*/api/metrics", () => HttpResponse.json(computeMetrics(seedIncidents(), { dateKind: "claim", from: null, to: null, provider: null, branch: null }, "production"))));
    show();
    expect(await screen.findByText(t.envProduction)).toBeInTheDocument();
    expect(screen.queryByText(t.envTest)).not.toBeInTheDocument();
    expect(screen.getByText(t.subtitle("Producción"))).toBeInTheDocument();
  });

  it("keeps email and Glovo apart, each with its own figures", async () => {
    show();
    const email = await channel(t.channels.email);
    const glovo = await channel(t.channels.glovo);
    expect(kpi(email, t.kpi.claimed)).toBe("3");
    expect(kpi(email, t.kpi.recovered)).toBe("1");
    expect(kpi(email, t.kpi.recoveredAmount)).toBe("12,00 €");
    expect(kpi(glovo, t.kpi.claimed)).toBe("1");
    expect(kpi(glovo, t.kpi.claimedAmount)).toBe("10,00 €");
    expect(kpi(glovo, t.kpi.recoveredAmount)).toBe("8,00 €");
    // No figure mixes the two channels.
    expect(email).not.toHaveTextContent("10,00 €");
  });

  it("is only available to roles that read metrics, and a global manager can", async () => {
    setScenario({ role: "global_manager" });
    show();
    expect(await channel(t.channels.email)).toBeInTheDocument();
  });
});

describe("the date criterion is always stated (RF-15)", () => {
  it("says which date every figure and the period use, and shows it in the filter", async () => {
    show();
    await channel(t.channels.email);
    expect(screen.getByText(t.criterion("Fecha de reclamación"))).toBeInTheDocument();
    expect(field(t.filters.dateKind)).toHaveValue("claim");
  });

  it("changing the date criterion changes what is counted, and the statement follows", async () => {
    show();
    await channel(t.channels.email);
    await userEvent.selectOptions(field(t.filters.dateKind), "recovery");
    await userEvent.type(field(t.filters.from), "01/11/2026");
    await waitFor(() => expect(screen.getByText(t.criterion("Fecha de recuperación"))).toBeInTheDocument());
    await waitFor(async () => expect(kpi(await channel(t.channels.email), t.kpi.claimed)).toBe("1"));
    expect(screen.getByTestId("where")).toHaveTextContent("dateKind=recovery");
    expect(screen.getByTestId("where")).toHaveTextContent("from=2026-11-01");
  });

  it("the dates are typed as dd/mm/aaaa and a date that does not exist changes nothing", async () => {
    show();
    await channel(t.channels.email);
    expect(field(t.filters.from)).toHaveAttribute("placeholder", "dd/mm/aaaa");
    await userEvent.type(field(t.filters.from), "31/02/2026");
    expect(await screen.findByText(es.dates.invalid)).toBeInTheDocument();
    expect(screen.getByTestId("where")).not.toHaveTextContent("from=");
  });

  it("filters by provider and keeps the filters in the address", async () => {
    show();
    await channel(t.channels.email);
    await userEvent.selectOptions(field(t.filters.provider), "uber eats");
    await waitFor(async () => expect(kpi(await channel(t.channels.email), t.kpi.claimed)).toBe("2"));
    expect(screen.getByTestId("where")).toHaveTextContent("provider=uber+eats");
  });

  it("restores the filters from the address", async () => {
    show("/panel?dateKind=incident&from=2026-11-12");
    await channel(t.channels.email);
    expect(field(t.filters.dateKind)).toHaveValue("incident");
    expect(field(t.filters.from)).toHaveValue("12/11/2026");
    expect(screen.getByText(t.criterion("Fecha de la incidencia"))).toBeInTheDocument();
  });
});

describe("the recovered amount is explicit and absent values are not zero (RF-15, RNF-13)", () => {
  it("shows the recovered amount apart from the claimed one", async () => {
    show();
    const email = await channel(t.channels.email);
    expect(kpi(email, t.kpi.claimedAmount)).toContain("32,50 €");
    expect(kpi(email, t.kpi.recoveredAmount)).toBe("12,00 €");
  });

  it("an empty period says there is no data, with no amount shown as zero", async () => {
    show("/panel?dateKind=claim&from=2030-01-01");
    expect(await screen.findByText(t.noPeriod)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: t.channels.email })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\b0,00|\b0 €/);
  });

  it("with claims but nothing recovered, says so instead of showing zero", async () => {
    show("/panel?provider=just+eat");
    const email = await channel(t.channels.email);
    expect(kpi(email, t.kpi.recoveredAmount)).toBe(t.noRecovery);
    expect(kpi(email, t.kpi.recovered)).toBe("0");
  });

  it("the rate is not calculable with the recovery date, and a real zero is shown as zero", async () => {
    show("/panel?provider=just+eat&dateKind=recovery");
    expect(kpi(await channel(t.channels.email), t.kpi.rate)).toBe(t.rateUnknown);
  });

  it("with a claim and no recovery the rate is a real 0 %, not unknown", async () => {
    show("/panel?provider=just+eat");
    expect(kpi(await channel(t.channels.email), t.kpi.rate)).toBe("0,00 %");
  });
});

describe("incomplete data carries a warning (UI-06)", () => {
  it("warns that the total is incomplete and says how many incidents have no amount", async () => {
    show();
    expect(await screen.findByText("Hay 1 incidencia sin importe: los totales están incompletos.")).toBeInTheDocument();
    const email = await channel(t.channels.email);
    const claimed = within(email).getByText(t.kpi.claimedAmount).closest(".kpi") as HTMLElement;
    expect(within(claimed).getByText(t.incomplete)).toBeInTheDocument();
    expect(claimed).toHaveTextContent(t.incompleteNote(1));
  });

  it("flags only the channel that is incomplete", async () => {
    show();
    const glovo = await channel(t.channels.glovo);
    expect(within(glovo).queryByText(t.incomplete)).not.toBeInTheDocument();
  });

  it("does not warn when every amount is known", async () => {
    show("/panel?provider=glovo");
    await channel(t.channels.glovo);
    await waitFor(() => expect(screen.queryByText(/incidencia sin importe/)).not.toBeInTheDocument());
  });

  it("marks the breakdown row whose amount is missing, with no total shown for it", async () => {
    show();
    const table = await screen.findByRole("table", { name: t.breakdown.title });
    const row = within(table).getByText("Just Eat").closest("tr") as HTMLElement;
    expect(row).toHaveTextContent(t.noData);
    expect(within(row).getByText("1", { selector: ".pill" })).toBeInTheDocument();
  });

  it("shows a missing branch as Sin sucursal in the breakdown", async () => {
    const created = await api("/api/incidents/manual", { provider: "glovo", orderId: "GL-9", incidentDate: "2026-11-21", incidentTime: null, branch: null, claimAmount: "5.00", providerCosts: null, total: null, description: null });
    await api(`/api/incidents/${created.id}/claim`, { claimDate: "2026-11-21" });
    show();
    const table = await screen.findByRole("table", { name: t.breakdown.title });
    expect(within(table).getByText(es.values.noBranch)).toBeInTheDocument();
  });
});

describe("the criteria are the ones the administrator decided (P-04)", () => {
  it("no longer presents the date default, the rate or the age as design examples", async () => {
    show();
    await channel(t.channels.email);
    expect(screen.queryByText(new RegExp(t.examples))).not.toBeInTheDocument();
    expect(screen.queryByText(/Pendiente de decisión \(P-04\)/)).not.toBeInTheDocument();
  });

  it("gives the rate as recoveries over claims, with its digits and no example note", async () => {
    show();
    const email = await channel(t.channels.email);
    const card = within(email).getByText(t.kpi.rate).closest(".kpi") as HTMLElement;
    expect(card).toHaveTextContent("33,33 %"); // 1 recovery of 3 claims
    expect(card).not.toHaveTextContent(t.rateExample);
  });
});

describe("claims waiting for a result and their age (RF-15)", () => {
  it("lists them with how long they have waited, the oldest first", async () => {
    show();
    const section = (await screen.findByRole("heading", { level: 2, name: t.pending.title })).closest("section") as HTMLElement;
    const rows = within(within(section).getByRole("table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("inc-006");
    expect(rows[0]).toHaveTextContent(t.pending.age(3));
    expect(rows[1]).toHaveTextContent("inc-001");
    expect(rows[1]).toHaveTextContent(t.pending.age(2));
  });

  it("states the age criterion and links to each incident", async () => {
    show();
    const section = (await screen.findByRole("heading", { level: 2, name: t.pending.title })).closest("section") as HTMLElement;
    expect(within(section).getByText(t.pending.note)).toBeInTheDocument();
    expect(within(section).queryByText(/Pendiente de decisión/)).not.toBeInTheDocument();
    expect(within(section).getByRole("link", { name: "inc-001" })).toHaveAttribute("href", "/incidencias/inc-001");
  });

  it("a claim that gets a result leaves the list", async () => {
    await api("/api/incidents/inc-001/result", { result: "resolved", recoveredAmount: "12.50", recoveryDate: "2026-11-21" });
    show();
    const section = (await screen.findByRole("heading", { level: 2, name: t.pending.title })).closest("section") as HTMLElement;
    expect(within(section).queryByRole("link", { name: "inc-001" })).not.toBeInTheDocument();
    expect(within(section).getByRole("link", { name: "inc-006" })).toBeInTheDocument();
  });

  it("says so when none is waiting", async () => {
    show("/panel?provider=glovo");
    expect(await screen.findByText(t.pending.empty)).toBeInTheDocument();
  });
});

describe("states of the dashboard", () => {
  it("shows an explicit empty state when there is no data at all", async () => {
    setScenario({ emptyData: true });
    show();
    expect(await screen.findByText(t.noPeriod)).toBeInTheDocument();
  });

  it("reports an error with a way to try again", async () => {
    setScenario({ failure: "server" });
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.readFailed);
    expect(screen.getByRole("button", { name: es.common.retry })).toBeInTheDocument();
  });

  it("removes the filters with one action", async () => {
    show("/panel?provider=glovo&dateKind=recovery");
    await channel(t.channels.email);
    await userEvent.click(screen.getByRole("button", { name: t.filters.clear }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent(/^\/panel$/));
    expect(field(t.filters.provider)).toHaveValue("");
  });
});
