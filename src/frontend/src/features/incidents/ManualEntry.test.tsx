/* eslint-disable @typescript-eslint/no-explicit-any -- responses are inspected loosely in these tests */
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

const server = setupServer(...handlers);
const t = es.manual;
const requests: string[] = [];

const show = () => renderAt("/incidencias/nueva", <AppRoutes areas={areas} />);
const api = async (path: string, body?: unknown) =>
  (await fetch(`${location.origin}${path}`, { method: body === undefined ? "GET" : "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json() as Promise<any>;
const total = async () => (await api("/api/incidents")).total as number;

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  server.events.on("request:start", ({ request }) => {
    if (request.method === "POST" && request.url.includes("/api/incidents/manual")) requests.push(new URL(request.url).pathname);
  });
});
beforeEach(() => {
  requests.length = 0;
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const label = (text: string) => screen.getByLabelText(text);
const type = (text: string, value: string) => userEvent.type(label(text), value);

async function fillNew(overrides: Record<string, string> = {}) {
  const values: Record<string, string> = { provider: "uber eats", orderId: "UE-200001", date: "21/11/2026", claim: "18,75", ...overrides };
  await screen.findByRole("form", { name: es.titles.manualEntry });
  await userEvent.selectOptions(label(t.provider), values.provider);
  await type(t.orderId, values.orderId);
  await type(t.date, values.date);
  if (values.claim) await type(t.claimAmount, values.claim);
  if (values.time) await type(t.time, values.time);
  if (values.branch) await userEvent.selectOptions(label(t.branch), values.branch);
  if (values.costs) await type(t.providerCosts, values.costs);
  if (values.total) await type(t.total, values.total);
  if (values.description) await type(t.description, values.description);
}
const check = () => userEvent.click(screen.getByRole("button", { name: t.check }));

describe("the form (RF-22)", () => {
  it("has the same business fields as the XLSX and says nothing is guessed", async () => {
    show();
    await screen.findByRole("form", { name: es.titles.manualEntry });
    for (const name of [t.provider, t.orderId, t.date, t.time, t.branch, t.claimAmount, t.providerCosts, t.total, t.description]) {
      expect(label(name)).toBeInTheDocument();
    }
    expect(screen.getByText(t.timeHelp)).toBeInTheDocument();
    expect(screen.getByText(t.orderIdHelp)).toBeInTheDocument();
  });

  it("offers no way to send an email, and shows that decision as pending (P-12)", async () => {
    show();
    await screen.findByRole("form", { name: es.titles.manualEntry });
    expect(screen.getByText(/Pendiente de decisión \(P-12\)/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(t.emailText))).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/correo|email|enviar/i)).not.toBeInTheDocument();
  });

  it("asks for the three required values and sends nothing without them", async () => {
    show();
    await screen.findByRole("form", { name: es.titles.manualEntry });
    await check();
    const alerts = (await screen.findAllByRole("alert")).map((a) => a.textContent);
    expect(alerts).toEqual(expect.arrayContaining([t.errors.provider, t.errors.orderId, t.errors.date]));
    expect(requests).toHaveLength(0);
  });

  it("rejects an amount that is not a number", async () => {
    show();
    await fillNew({ claim: "doce" });
    await check();
    expect(await screen.findByText(t.errors.amount)).toBeInTheDocument();
    expect(requests).toHaveLength(0);
  });

  it("does not accept an Order ID of only spaces, but keeps any other exactly as typed", async () => {
    show();
    await fillNew({ orderId: "   " });
    await check();
    expect(await screen.findByText(t.errors.orderId)).toBeInTheDocument();
  });
});

describe("a duplicate or a conflict is rejected (UI-09, RF-22)", () => {
  const existing = { provider: "uber eats", orderId: "UE-098001", date: "10/11/2026", time: "19:40", branch: "centro", claim: "12,50" };

  it("a duplicate is rejected with a clear message, with nothing to confirm and nothing created", async () => {
    show();
    await fillNew(existing);
    await check();
    const notice = (await screen.findByText(t.duplicateTitle)).closest(".notice") as HTMLElement;
    expect(notice).toHaveTextContent(t.duplicateText);
    expect(screen.queryByRole("button", { name: t.confirm })).not.toBeInTheDocument();
    expect(requests).toEqual(["/api/incidents/manual/check"]);
    expect(await total()).toBe(6);
  });

  it("a conflict shows both versions with the difference marked, and nothing to confirm", async () => {
    show();
    await fillNew({ ...existing, claim: "99,00" });
    await check();
    const notice = (await screen.findByText(t.conflictTitle)).closest(".notice") as HTMLElement;
    expect(notice).toHaveTextContent(t.conflictText);
    const row = within(notice).getByRole("rowheader", { name: es.review.compare.fields.claimAmount }).closest("tr") as HTMLElement;
    expect(row).toHaveClass("diff");
    expect(row).toHaveTextContent("99,00 €");
    expect(row).toHaveTextContent("12,50 €");
    expect(screen.queryByRole("button", { name: t.confirm })).not.toBeInTheDocument();
    expect(await total()).toBe(6);
  });

  it("lets the user correct the data and try again after a rejection", async () => {
    show();
    await fillNew({ ...existing, claim: "99,00" });
    await check();
    await screen.findByText(t.conflictTitle);
    const order = label(t.orderId);
    await userEvent.clear(order);
    await userEvent.type(order, "UE-300001");
    await check();
    expect(await screen.findByRole("heading", { level: 2, name: t.reviewTitle })).toBeInTheDocument();
  });
});

describe("a new entry needs review and confirmation before it is saved (UI-09)", () => {
  it("shows what will be saved, and says it is not saved yet", async () => {
    show();
    await fillNew({ time: "20:22", branch: "centro", description: "Falta una bebida" });
    await check();
    const review = (await screen.findByRole("heading", { level: 2, name: t.reviewTitle })).closest("section") as HTMLElement;
    expect(review).toHaveTextContent(t.notSaved);
    expect(review).toHaveTextContent("UE-200001");
    expect(review).toHaveTextContent("2026-11-21 20:22");
    expect(review).toHaveTextContent("18,75 €");
    expect(review).toHaveTextContent("Falta una bebida");
    expect(within(review).getByText(/Pendiente de decisión \(P-12\)/)).toBeInTheDocument();
    // Not saved: the server still has the same incidents.
    expect(await total()).toBe(6);
    expect(requests).toEqual(["/api/incidents/manual/check"]);
  });

  it("saves only when the administrator confirms, without email, and links to it", async () => {
    show();
    await fillNew();
    await check();
    await userEvent.click(await screen.findByRole("button", { name: t.confirm }));
    const done = (await screen.findByText(t.savedTitle)).closest(".notice") as HTMLElement;
    expect(done).toHaveTextContent(t.savedText);
    expect(await total()).toBe(7);
    expect(requests).toEqual(["/api/incidents/manual/check", "/api/incidents/manual"]);

    const saved = (await api("/api/incidents")).items.find((i: any) => i.orderId === "UE-200001");
    expect(saved.status).toBe("imported_no_email");
    expect(saved.batchId).toBeNull();
    await userEvent.click(within(done).getByRole("link", { name: t.open }));
    expect(await screen.findByRole("heading", { level: 1, name: es.incidents.detailTitle("UE-200001") })).toBeInTheDocument();
    expect(screen.queryByText(es.incidents.email.pendingTitle)).not.toBeInTheDocument();
    expect(screen.getByText(es.incidents.fields.manualEntry, { selector: "dd" })).toBeInTheDocument();
  });

  it("lets the administrator go back and edit without losing what was typed", async () => {
    show();
    await fillNew({ description: "Nota" });
    await check();
    await userEvent.click(await screen.findByRole("button", { name: t.edit }));
    expect(label(t.orderId)).toHaveValue("UE-200001");
    expect(label(t.claimAmount)).toHaveValue("18,75");
    expect(label(t.description)).toHaveValue("Nota");
    expect(await total()).toBe(6);
  });

  it("confirming twice quickly saves once", async () => {
    show();
    await fillNew();
    await check();
    await userEvent.dblClick(await screen.findByRole("button", { name: t.confirm }));
    await screen.findByText(t.savedTitle);
    expect(requests.filter((p) => p === "/api/incidents/manual")).toHaveLength(1);
    expect(await total()).toBe(7);
  });

  it("an entry saved without optional values keeps them absent, never as zero or midnight", async () => {
    show();
    await fillNew({ claim: "" });
    await check();
    await userEvent.click(await screen.findByRole("button", { name: t.confirm }));
    await screen.findByText(t.savedTitle);
    const saved = (await api("/api/incidents")).items.find((i: any) => i.orderId === "UE-200001");
    expect(saved).toMatchObject({ branch: null, claimAmount: null, providerCosts: null, total: null, description: null, incidentTime: null });
  });

  it("keeps an amount with more than two decimals and an Order ID exactly as typed", async () => {
    show();
    await fillNew({ orderId: "ab-12x", claim: "0,1234", costs: "3,5", total: "0" });
    await check();
    await userEvent.click(await screen.findByRole("button", { name: t.confirm }));
    await screen.findByText(t.savedTitle);
    const saved = (await api("/api/incidents")).items.find((i: any) => i.orderId === "ab-12x");
    expect(saved).toMatchObject({ claimAmount: "0.1234", providerCosts: "3.5", total: "0" });
  });

  it("works for Glovo too, still without email", async () => {
    show();
    await fillNew({ provider: "glovo", orderId: "GL-1" });
    await check();
    await userEvent.click(await screen.findByRole("button", { name: t.confirm }));
    await screen.findByText(t.savedTitle);
    const saved = (await api("/api/incidents")).items.find((i: any) => i.orderId === "GL-1");
    expect(saved).toMatchObject({ channel: "glovo", status: "imported_no_email" });
  });

  it("can start another entry afterwards, with an empty form", async () => {
    show();
    await fillNew();
    await check();
    await userEvent.click(await screen.findByRole("button", { name: t.confirm }));
    await userEvent.click(await screen.findByRole("button", { name: t.another }));
    expect(label(t.orderId)).toHaveValue("");
  });
});

describe("failures and races", () => {
  it("reports a failed check instead of failing silently", async () => {
    show();
    await fillNew();
    setScenario({ failure: "server" });
    await check();
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.generic);
    expect(screen.queryByRole("heading", { level: 2, name: t.reviewTitle })).not.toBeInTheDocument();
  });

  it("when saving fails it says so, keeps the review open and saves nothing", async () => {
    show();
    await fillNew();
    await check();
    const confirm = await screen.findByRole("button", { name: t.confirm });
    setScenario({ failure: "server" });
    await userEvent.click(confirm);
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.generic);
    setScenario({ failure: "none" });
    expect(await total()).toBe(6);
  });

  it("when someone else created the same key meanwhile, nothing is saved and it says why", async () => {
    show();
    await fillNew();
    await check();
    const confirm = await screen.findByRole("button", { name: t.confirm });
    await api("/api/incidents/manual", { provider: "uber eats", orderId: "UE-200001", incidentDate: "2026-11-21", incidentTime: null, branch: null, claimAmount: null, providerCosts: null, total: null, description: null });
    await userEvent.click(confirm);
    expect(await screen.findByRole("alert")).toHaveTextContent(t.raced);
    await waitFor(async () => expect(await total()).toBe(7));
  });
});

describe("only an administrator can create incidents", () => {
  it("a global manager is shown a denial instead of the form", async () => {
    setScenario({ role: "global_manager" });
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent(es.states.deniedTitle);
    expect(screen.queryByRole("form", { name: es.titles.manualEntry })).not.toBeInTheDocument();
  });
});

describe("dates and times are typed as dd/mm/aaaa and hh:mm", () => {
  it("uses text boxes with the Spanish format, not the browser's own date control", async () => {
    show();
    await screen.findByRole("form", { name: es.titles.manualEntry });
    expect(label(t.date)).toHaveAttribute("type", "text");
    expect(label(t.date)).toHaveAttribute("placeholder", "dd/mm/aaaa");
    expect(label(t.time)).toHaveAttribute("type", "text");
    expect(label(t.time)).toHaveAttribute("placeholder", "hh:mm");
    expect(document.querySelector('input[type="date"], input[type="time"]')).toBeNull();
  });

  it("rejects a date that does not exist instead of reading it as no date", async () => {
    show();
    await fillNew({ date: "31/02/2026" });
    await check();
    expect(await screen.findByText(es.dates.invalid)).toBeInTheDocument();
    expect(requests).toHaveLength(0);
  });

  it("rejects the ISO form and a two-digit year", async () => {
    show();
    await fillNew({ date: "2026-11-21" });
    await check();
    expect(await screen.findByText(es.dates.invalid)).toBeInTheDocument();
  });

  it("rejects a time that is not a 24-hour time", async () => {
    show();
    await fillNew({ time: "24:30" });
    await check();
    expect(await screen.findByText(es.dates.invalidTime)).toBeInTheDocument();
    expect(requests).toHaveLength(0);
  });

  it("sends the date in the ISO form the API takes, and the time as typed", async () => {
    show();
    await fillNew({ date: "5/1/2026", time: "9:05" });
    await check();
    await userEvent.click(await screen.findByRole("button", { name: t.confirm }));
    await screen.findByText(t.savedTitle);
    const saved = (await api("/api/incidents")).items.find((i: any) => i.orderId === "UE-200001");
    expect(saved).toMatchObject({ incidentDate: "2026-01-05", incidentTime: "09:05" });
  });
});
