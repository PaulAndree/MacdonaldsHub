import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { es } from "../i18n/es";
import AppRoutes from "./AppRoutes";
import { areas } from "./areas";
import { renderAt, sessionOf, stubSession } from "./testing";

afterEach(() => vi.unstubAllGlobals());

const show = (path: string) => renderAt(path, <AppRoutes areas={areas} />);
const navLabels = () =>
  within(screen.getByRole("navigation", { name: es.nav.label }))
    .getAllByRole("link")
    .map((link) => link.textContent);

describe("before a valid session (identity-access)", () => {
  it("shows a loading state and no navigation while the session is being read", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    show("/panel");
    expect(screen.getByRole("status")).toHaveTextContent(es.common.loading);
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("explains a missing or expired session (401) and offers to reload", async () => {
    stubSession({ code: "not_authenticated", message: "x" }, 401);
    show("/panel");
    expect(await screen.findByRole("heading", { level: 1, name: es.access.noSessionTitle })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(es.errors.noSession);
    expect(screen.getByRole("button", { name: es.access.reload })).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("explains that Google authenticated the user but they are not authorized (403)", async () => {
    stubSession({ code: "not_authorized", message: "x" }, 403);
    show("/panel");
    expect(await screen.findByRole("heading", { level: 1, name: es.access.notAuthorizedTitle })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Google le ha identificado correctamente");
    expect(screen.getByRole("alert")).toHaveTextContent("no está autorizada");
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: es.titles.dashboard })).not.toBeInTheDocument();
  });
});

describe("administrator", () => {
  it("sees every area and their identity, role and environment", async () => {
    stubSession(sessionOf("test"));
    show("/panel");
    expect(await screen.findByRole("heading", { level: 1, name: es.titles.dashboard })).toBeInTheDocument();
    expect(navLabels()).toEqual([
      es.nav.import,
      es.nav.incidents,
      es.nav.manualEntry,
      es.nav.dashboard,
      es.nav.queue,
    ]);
    const session = screen.getByText("usuario@example.test").closest(".session") as HTMLElement;
    expect(session).toHaveTextContent(es.roles.administrator);
    expect(session).toHaveTextContent(`${es.access.environment}: ${es.environments.test}`);
  });

  it("names the production environment too", async () => {
    stubSession(sessionOf("production"));
    show("/panel");
    expect(await screen.findByText(/Entorno: Producción/)).toBeInTheDocument();
  });
});

describe("global manager (consultation only)", () => {
  it("is offered only incidents and the dashboard", async () => {
    stubSession(sessionOf("test", "global_manager"));
    show("/panel");
    expect(await screen.findByRole("heading", { level: 1, name: es.titles.dashboard })).toBeInTheDocument();
    expect(navLabels()).toEqual([es.nav.incidents, es.nav.dashboard]);
    expect(screen.getByText(es.roles.global_manager, { exact: false })).toBeInTheDocument();
  });

  it("can open the areas the role allows", async () => {
    stubSession(sessionOf("test", "global_manager"));
    show("/incidencias");
    expect(await screen.findByRole("heading", { level: 1, name: es.titles.incidents })).toBeInTheDocument();
  });

  it.each([
    ["/correo", es.titles.queue],
    ["/importar", es.titles.import],
    ["/incidencias/nueva", es.titles.manualEntry],
  ])("typing %s shows a denial instead of the area (UI-10)", async (path, title) => {
    stubSession(sessionOf("test", "global_manager"));
    show(path);
    expect(await screen.findByRole("alert")).toHaveTextContent(es.states.deniedTitle);
    expect(screen.queryByRole("heading", { level: 1, name: title })).not.toBeInTheDocument();
  });
});

describe("session operation not available yet", () => {
  it("reports the problem on every route, with a way to try again, and offers no navigation", async () => {
    stubSession({ code: "not_found", message: "x" }, 404);
    show("/panel");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: es.common.retry })).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: es.titles.dashboard })).not.toBeInTheDocument();
  });

  it("asks for the session once, not in a loop, when it keeps failing", async () => {
    stubSession({ code: "not_found", message: "x" }, 404);
    show("/importar");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 400));
    const calls = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(calls.filter((call) => String(call[0]).endsWith("/api/session"))).toHaveLength(1);
  });
});

describe("areas that do not exist in this application", () => {
  it.each(["/administracion", "/administracion/autorizaciones", "/auditoria", "/diagnostico", "/guia"])(
    "%s is not a screen: the administrator here is the franchise's, not the technical team",
    async (path) => {
      stubSession(sessionOf("test"));
      show(path);
      expect(await screen.findByRole("heading", { level: 1, name: es.titles.notFound })).toBeInTheDocument();
    },
  );
});
