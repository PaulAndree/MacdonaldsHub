import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { es } from "../i18n/es";
import { areas } from "./areas";
import AppRoutes from "./AppRoutes";
import { renderAt, sessionOf, stubSession } from "./testing";

function at(path: string) {
  return renderAt(path, <AppRoutes areas={areas} />);
}

beforeEach(() => stubSession(sessionOf("production")));
afterEach(() => vi.unstubAllGlobals());

const routes: [string, string][] = [
  ["/importar", es.titles.import],
  ["/lotes/lote-0007", es.titles.batch],
  ["/incidencias", es.titles.incidents],
  ["/incidencias/nueva", es.titles.manualEntry],
  ["/incidencias/inc-001", es.titles.incident],
  ["/panel", es.titles.dashboard],
  ["/correo", es.titles.queue],
];

describe("routes", () => {
  it.each(routes)("%s opens its screen", async (path, title) => {
    at(path);
    expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
  });

  it("has no review guide in the standard build", async () => {
    at("/guia");
    expect(await screen.findByRole("heading", { level: 1, name: es.titles.notFound })).toBeInTheDocument();
  });

  it("sends the root to the import area", async () => {
    at("/");
    expect(await screen.findByRole("heading", { level: 1, name: es.titles.import })).toBeInTheDocument();
  });

  it("shows a Spanish not-found page with a way back for an unknown address", async () => {
    at("/no-existe");
    expect(await screen.findByRole("heading", { level: 1, name: es.titles.notFound })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: es.notFound.back })).toHaveAttribute("href", "/");
  });

  it("keeps the navigation visible on every route", async () => {
    at("/panel");
    expect(await screen.findByRole("navigation", { name: es.nav.label })).toBeInTheDocument();
  });
});
