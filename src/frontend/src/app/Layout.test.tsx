import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { es } from "../i18n/es";
import { areas } from "./areas";
import Layout from "./Layout";

function renderLayout(path = "/panel", visible = areas) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          element={
            <Layout
              areas={visible}
              banners={<div role="status">aviso</div>}
              session={<span>sesión</span>}
              footer="pie"
            />
          }
        >
          <Route path="*" element={<h1>Contenido</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("layout and navigation", () => {
  it("exposes the page landmarks and a skip link", () => {
    renderLayout();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: es.nav.label })).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveTextContent("Contenido");
    expect(screen.getByRole("contentinfo")).toHaveTextContent("pie");
    expect(screen.getByRole("link", { name: es.skipToContent })).toHaveAttribute("href", "#contenido");
  });

  it("offers every area it is given, in Spanish, and marks the current one", () => {
    renderLayout("/panel");
    const nav = screen.getByRole("navigation", { name: es.nav.label });
    for (const area of areas) {
      expect(within(nav).getByRole("link", { name: area.label })).toHaveAttribute("href", area.path);
    }
    expect(within(nav).getByRole("link", { name: es.nav.dashboard })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: es.nav.queue })).not.toHaveAttribute("aria-current");
  });

  it("shows only the areas passed to it", () => {
    renderLayout("/panel", areas.filter((a) => a.id === "dashboard"));
    const nav = screen.getByRole("navigation", { name: es.nav.label });
    expect(within(nav).getAllByRole("link")).toHaveLength(1);
  });

  it("renders the banners and session slots", () => {
    renderLayout();
    expect(screen.getByRole("status")).toHaveTextContent("aviso");
    expect(screen.getByText("sesión")).toBeInTheDocument();
  });
});
