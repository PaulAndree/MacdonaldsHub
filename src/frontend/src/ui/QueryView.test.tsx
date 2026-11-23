import { QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createQueryClient } from "../api/queryClient";
import { api } from "../api/client";
import QueryView from "./QueryView";

function List() {
  const query = useQuery({ queryKey: ["list"], queryFn: () => api.get<{ items: string[] }>("/api/list") });
  return (
    <QueryView query={query} isEmpty={(d) => d.items.length === 0} emptyTitle="Sin elementos">
      {(d) => <ul>{d.items.map((i) => <li key={i}>{i}</li>)}</ul>}
    </QueryView>
  );
}

function show(response: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(response));
  return render(
    <QueryClientProvider client={createQueryClient({ retryDelay: 0 })}>
      <List />
    </QueryClientProvider>,
  );
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("QueryView", () => {
  it("shows loading first and then the data", async () => {
    show(async () => json({ items: ["uno"] }));
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("uno")).toBeInTheDocument();
  });

  it("shows the empty state for an empty result", async () => {
    show(async () => json({ items: [] }));
    expect(await screen.findByText("Sin elementos")).toBeInTheDocument();
  });

  it("shows the denied state for a 403", async () => {
    show(async () => json({ code: "not_authorized", message: "x" }, 403));
    expect(await screen.findByText("Acceso denegado")).toBeInTheDocument();
  });

  it("shows an error with retry for a failed read", async () => {
    show(async () => Promise.reject(new TypeError("down")));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar la información");
    expect(screen.getByRole("button", { name: "Reintentar la carga" })).toBeInTheDocument();
  });
});
