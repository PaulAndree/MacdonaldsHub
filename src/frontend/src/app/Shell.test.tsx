import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { exampleEs } from "../example/strings";
import { exampleUi } from "../example/ui";
import { es } from "../i18n/es";
import AppRoutes from "./AppRoutes";
import { areas } from "./areas";
import { renderAt, sessionOf, stubSession } from "./testing";


afterEach(() => vi.unstubAllGlobals());

const routes = [
  "/importar",
  "/lotes/lote-0007",
  "/incidencias",
  "/incidencias/nueva",
  "/panel",
  "/correo",
];

describe("example build frame (UI-11, RF-12)", () => {
  beforeEach(() => stubSession(sessionOf("test")));

  it.each(routes)("%s shows the example-data notice and the versions", async (route) => {
    renderAt(route, <AppRoutes areas={areas} exampleUi={exampleUi} />);
    expect(screen.getByText(exampleEs.banner)).toBeInTheDocument();
    const footer = screen.getByRole("contentinfo");
    expect(footer).toHaveTextContent(exampleEs.footer.designVersion);
    expect(footer).toHaveTextContent("contrato");
  });

  it("shows the design version it was built from, or says it has no tag", () => {
    renderAt("/panel", <AppRoutes areas={areas} exampleUi={exampleUi} />);
    expect(screen.getByRole("contentinfo")).toHaveTextContent(exampleEs.footer.unreleased);
  });
});

describe("standard build frame", () => {
  it("shows neither the example notice nor a version footer, and has no review guide", async () => {
    stubSession(sessionOf("production"));
    renderAt("/guia", <AppRoutes areas={areas} />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(es.titles.notFound));
    expect(screen.queryByText(exampleEs.banner)).not.toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeEmptyDOMElement();
  });

  it("shows no example notice in the test environment without example data", async () => {
    stubSession(sessionOf("test"));
    renderAt("/panel", <AppRoutes areas={areas} />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    expect(screen.queryByText(exampleEs.banner)).not.toBeInTheDocument();
  });

  it("keeps the frame and the brand when the session cannot be read, with no environment banner", async () => {
    stubSession({ code: "not_authenticated", message: "x" }, 401);
    renderAt("/panel", <AppRoutes areas={areas} />);
    expect(await screen.findByRole("heading", { level: 1, name: es.access.noSessionTitle })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });
});
