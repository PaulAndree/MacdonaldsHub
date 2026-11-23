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
const t = es.incidents;
const a = t.actions;
const posts: string[] = [];

const show = (path: string) => renderAt(path, <AppRoutes areas={areas} />);
const call = async (path: string, body?: unknown) =>
  (await fetch(`${location.origin}${path}`, { method: body === undefined ? "GET" : "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json() as Promise<any>;
const incident = async (id: string) => (await call(`/api/incidents/${id}`)).incident;
const claimViaApi = (id: string) => call(`/api/incidents/${id}/claim`, { claimDate: "2026-11-21" });
const section = async (name: string) => (await screen.findByRole("heading", { level: 2, name })).closest("section") as HTMLElement;
const dd = (root: HTMLElement, label: string) => (within(root).getByText(label).nextElementSibling as HTMLElement).textContent;

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  server.events.on("request:start", ({ request }) => {
    if (request.method === "POST" && /\/(claim|result|corrections)$/.test(request.url)) posts.push(request.url);
  });
});
beforeEach(() => {
  posts.length = 0;
  resetScenario();
  setScenario({ latencyMs: 0, processingMs: 0 });
  resetStore();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("claim an incident that has no email (RF-21)", () => {
  it("offers it, and shows the claim channel as a pending decision (P-11)", async () => {
    show("/incidencias/inc-003");
    const card = await section(a.claim.title);
    expect(within(card).getByText(/Pendiente de decisión \(P-11\)/)).toBeInTheDocument();
    expect(card).toHaveTextContent(a.claim.channelNote);
  });

  it("asks for the date and does not send anything without it", async () => {
    show("/incidencias/inc-003");
    await userEvent.click(within(await section(a.claim.title)).getByRole("button", { name: a.claim.submit }));
    expect(await screen.findByRole("alert")).toHaveTextContent(a.claim.dateRequired);
    expect(posts).toHaveLength(0);
    expect((await incident("inc-003")).status).toBe("imported_no_email");
  });

  it("records the claim with its date, apart from the incident and recovery dates", async () => {
    show("/incidencias/inc-003");
    const card = await section(a.claim.title);
    await userEvent.type(within(card).getByLabelText(a.claim.date), "21/11/2026");
    await userEvent.click(within(card).getByRole("button", { name: a.claim.submit }));

    expect(await screen.findByText(a.claim.done)).toBeInTheDocument();
    const dates = await section(t.sections.dates);
    await waitFor(() => expect(dd(dates, t.dates.claim)).toBe("2026-11-21"));
    expect(dd(dates, t.dates.incident)).toBe("2026-11-12");
    expect(dd(dates, t.dates.recovery)).toBe(t.noRecovery);
    expect(within(await section(t.sections.result)).getByText(t.status.claimed, { selector: ".pill" })).toBeInTheDocument();
    // The claim is done: the form is replaced by the one to record the result.
    expect(screen.queryByRole("heading", { level: 2, name: a.claim.title })).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 2, name: a.result.title })).toBeInTheDocument();
    expect((await incident("inc-003")).claimDate).toBe("2026-11-21");
  });

  it("is also offered for a manual entry, which has no email", async () => {
    const created = await call("/api/incidents/manual", { provider: "uber eats", orderId: "UE-200001", incidentDate: "2026-11-21", incidentTime: null, branch: "centro", claimAmount: "18.75", providerCosts: null, total: null, description: null });
    show(`/incidencias/${created.id}`);
    expect(await screen.findByRole("heading", { level: 2, name: a.claim.title })).toBeInTheDocument();
  });

  it("is not offered when an email is pending, failed or already claimed it", async () => {
    show("/incidencias/inc-002");
    await screen.findByText(t.email.errorTitle);
    expect(screen.queryByRole("heading", { level: 2, name: a.claim.title })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: a.result.title })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: a.correct.title })).not.toBeInTheDocument();
  });
});

describe("record the result with an explicit recovered amount (UI-05, RF-21)", () => {
  async function openClaimed() {
    await claimViaApi("inc-003");
    posts.length = 0; // the set-up request does not count
    show("/incidencias/inc-003");
    return section(a.result.title);
  }
  const fill = async (card: HTMLElement, amount: string, date = "") => {
    if (amount) await userEvent.type(within(card).getByLabelText(a.result.amount), amount);
    if (date) await userEvent.type(within(card).getByLabelText(a.result.date), date);
  };

  it("records a partial recovery next to the claimed amount, without assuming it was all recovered", async () => {
    const card = await openClaimed();
    await fill(card, "12,50", "25/11/2026");
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));

    expect(await screen.findByText(a.result.done)).toBeInTheDocument();
    const result = await section(t.sections.result);
    await waitFor(() => expect(dd(result, t.result.recovered)).toBe("12,50 €"));
    expect(dd(result, t.result.claimed)).toBe("30,00 €");
    expect(within(result).getByText(t.status.resolved, { selector: ".pill" })).toBeInTheDocument();
    expect(within(result).getByText(t.result.notePartial)).toBeInTheDocument();
    // The server received the digits with a point, unchanged.
    const saved = await incident("inc-003");
    expect(saved.recoveredAmount).toBe("12.50");
    expect(saved.recoveryDate).toBe("2026-11-25");
    expect(saved.claimAmount).toBe("30.00");
  });

  it("keeps an amount with more than two decimals exactly", async () => {
    const card = await openClaimed();
    await fill(card, "0,1234");
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    await screen.findByText(a.result.done);
    expect((await incident("inc-003")).recoveredAmount).toBe("0.1234");
  });

  it("rejects an amount that is not a number and sends nothing", async () => {
    const card = await openClaimed();
    for (const bad of ["abc", "12,50 €", "1.234,50"]) {
      const box = within(card).getByLabelText(a.result.amount);
      await userEvent.clear(box);
      await userEvent.type(box, bad);
      await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
      expect(await within(card).findByRole("alert")).toHaveTextContent(a.result.invalidAmount);
    }
    expect(posts).toHaveLength(0);
    expect((await incident("inc-003")).status).toBe("claimed");
  });

  it("an empty amount stays absent, never zero", async () => {
    const card = await openClaimed();
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    await screen.findByText(a.result.done);
    expect((await incident("inc-003")).recoveredAmount).toBeNull();
    const result = await section(t.sections.result);
    await waitFor(() => expect(dd(result, t.result.recovered)).toBe(t.noRecovery));
  });

  it("an explicit zero is a real value, different from an empty box", async () => {
    const card = await openClaimed();
    await fill(card, "0");
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    await screen.findByText(a.result.done);
    expect((await incident("inc-003")).recoveredAmount).toBe("0");
    await waitFor(async () => expect(dd(await section(t.sections.result), t.result.recovered)).toBe("0 €"));
  });

  it("can record a rejection", async () => {
    const card = await openClaimed();
    await userEvent.selectOptions(within(card).getByLabelText(a.result.kind), "rejected");
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    await screen.findByText(a.result.done);
    expect((await incident("inc-003")).status).toBe("rejected");
    expect(within(await section(t.sections.result)).getByText(t.status.rejected, { selector: ".pill" })).toBeInTheDocument();
  });

  it("registers the change in the history with who did it", async () => {
    const card = await openClaimed();
    await fill(card, "12,50");
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    await screen.findByText(a.result.done);
    const history = await section(t.sections.history);
    await waitFor(() => expect(history).toHaveTextContent(`${t.history.kinds.result}: ${t.history.fields.recoveredAmount}`));
    expect(history).toHaveTextContent("12,50 €");
    expect(history).toHaveTextContent("admin-1");
  });

  it("says so when it fails, and the incident stays as it was", async () => {
    const card = await openClaimed();
    await fill(card, "12,50");
    setScenario({ failure: "server" });
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    expect(await within(card).findByRole("alert")).toHaveTextContent(es.errors.generic);
    setScenario({ failure: "none" });
    expect((await incident("inc-003")).status).toBe("claimed");
  });

  it("with a double click, records once", async () => {
    const card = await openClaimed();
    await fill(card, "12,50");
    await userEvent.dblClick(within(card).getByRole("button", { name: a.result.submit }));
    await screen.findByText(a.result.done);
    expect(posts.filter((url) => url.endsWith("/result"))).toHaveLength(1);
  });
});

describe("audited correction of a result (UI-05, RF-21)", () => {
  const correctionCard = () => section(a.correct.title);

  it("starts from the recorded values and does not allow a correction that changes nothing", async () => {
    show("/incidencias/inc-004");
    const card = await correctionCard();
    expect(within(card).getByLabelText(a.result.amount)).toHaveValue("12,00");
    expect(within(card).getByLabelText(a.result.date)).toHaveValue("15/11/2026");
    expect(within(card).getByText(a.correct.unchanged)).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: a.correct.submit })).toBeDisabled();
    expect(card).toHaveTextContent("No deshace la importación ni afecta a ningún correo");
  });

  it("requires the reason, and sends nothing without it", async () => {
    show("/incidencias/inc-004");
    const card = await correctionCard();
    const amount = within(card).getByLabelText(a.result.amount);
    await userEvent.clear(amount);
    await userEvent.type(amount, "8,00");
    await userEvent.click(within(card).getByRole("button", { name: a.correct.submit }));
    expect(await within(card).findByRole("alert")).toHaveTextContent(a.correct.reasonRequired);
    expect(posts).toHaveLength(0);
  });

  it("records the correction in the history with the previous value, the new one and the reason", async () => {
    show("/incidencias/inc-004");
    const card = await correctionCard();
    const amount = within(card).getByLabelText(a.result.amount);
    await userEvent.clear(amount);
    await userEvent.type(amount, "8,00");
    await userEvent.type(within(card).getByLabelText(a.correct.reason), "El proveedor devolvió solo 8,00.");
    await userEvent.click(within(card).getByRole("button", { name: a.correct.submit }));

    expect(await screen.findByText(a.correct.done)).toBeInTheDocument();
    const result = await section(t.sections.result);
    await waitFor(() => expect(dd(result, t.result.recovered)).toBe("8,00 €"));
    const history = await section(t.sections.history);
    const row = (await within(history).findByText(/Corrección: Importe recuperado/)).closest("tr") as HTMLElement;
    expect(row).toHaveClass("correction");
    expect(row).toHaveTextContent("12,00 € → 8,00 €");
    expect(row).toHaveTextContent("El proveedor devolvió solo 8,00.");
    expect(row).toHaveTextContent("admin-1");
  });

  it("does not touch the import or any email: the incident keeps its batch and its earlier history", async () => {
    show("/incidencias/inc-004");
    const before = await call("/api/incidents/inc-004");
    const card = await correctionCard();
    const amount = within(card).getByLabelText(a.result.amount);
    await userEvent.clear(amount);
    await userEvent.type(amount, "9,00");
    await userEvent.type(within(card).getByLabelText(a.correct.reason), "Corregido.");
    await userEvent.click(within(card).getByRole("button", { name: a.correct.submit }));
    await screen.findByText(a.correct.done);
    const after = await call("/api/incidents/inc-004");
    expect(after.incident.batchId).toBe(before.incident.batchId);
    expect(after.incident.claimAmount).toBe(before.incident.claimAmount);
    expect(after.history.slice(0, before.history.length)).toEqual(before.history);
    expect(after.history.length).toBeGreaterThan(before.history.length);
  });

  it("a correction can change the result kind, which changes the status", async () => {
    show("/incidencias/inc-004");
    const card = await correctionCard();
    await userEvent.selectOptions(within(card).getByLabelText(a.result.kind), "rejected");
    await userEvent.type(within(card).getByLabelText(a.correct.reason), "Fue rechazada.");
    await userEvent.click(within(card).getByRole("button", { name: a.correct.submit }));
    await screen.findByText(a.correct.done);
    expect((await incident("inc-004")).status).toBe("rejected");
  });

  it("can correct a result already corrected before", async () => {
    show("/incidencias/inc-005");
    const card = await correctionCard();
    expect(within(card).getByLabelText(a.result.amount)).toHaveValue("8,00");
  });
});

describe("only an administrator changes results", () => {
  it("a global manager sees the data and the history but no form", async () => {
    setScenario({ role: "global_manager" });
    show("/incidencias/inc-004");
    await screen.findByRole("heading", { level: 2, name: t.sections.history });
    expect(screen.queryByRole("heading", { level: 2, name: a.correct.title })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: a.correct.submit })).not.toBeInTheDocument();
  });

  it("the API refuses a change from a global manager and nothing changes", async () => {
    setScenario({ role: "global_manager" });
    const response = await fetch(`${location.origin}/api/incidents/inc-003/claim`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ claimDate: "2026-11-21" }) });
    expect(response.status).toBe(403);
    setScenario({ role: "administrator" });
    expect((await incident("inc-003")).status).toBe("imported_no_email");
  });
});

describe("dates in the forms are typed as dd/mm/aaaa", () => {
  it("rejects a claim date that does not exist and sends nothing", async () => {
    show("/incidencias/inc-003");
    const card = await section(a.claim.title);
    expect(within(card).getByLabelText(a.claim.date)).toHaveAttribute("placeholder", "dd/mm/aaaa");
    await userEvent.type(within(card).getByLabelText(a.claim.date), "31/04/2026");
    await userEvent.click(within(card).getByRole("button", { name: a.claim.submit }));
    expect(await within(card).findByRole("alert")).toHaveTextContent(es.dates.invalid);
    expect(posts).toHaveLength(0);
  });

  it("rejects a recovery date that does not exist instead of dropping it", async () => {
    await claimViaApi("inc-003");
    posts.length = 0;
    show("/incidencias/inc-003");
    const card = await section(a.result.title);
    await userEvent.type(within(card).getByLabelText(a.result.date), "30/02/2026");
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    expect(await within(card).findByText(es.dates.invalid)).toBeInTheDocument();
    expect(posts).toHaveLength(0);
    expect((await incident("inc-003")).status).toBe("claimed");
  });

  it("a recovery date is optional: empty is accepted and stays absent", async () => {
    await claimViaApi("inc-003");
    show("/incidencias/inc-003");
    const card = await section(a.result.title);
    await userEvent.click(within(card).getByRole("button", { name: a.result.submit }));
    await screen.findByText(a.result.done);
    expect((await incident("inc-003")).recoveryDate).toBeNull();
  });
});
