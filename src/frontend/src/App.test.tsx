import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function mockFetch(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(String(input), init),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(cleanup);

describe("technical screen", () => {
  it("shows the authenticated identity and role", async () => {
    mockFetch(() => json({ identifier: "ana", email: "ana@example.test", role: "administrator" }));
    render(<App />);
    expect(await screen.findByText("ana@example.test")).toBeInTheDocument();
    expect(screen.getByText("administrator")).toBeInTheDocument();
  });

  it("explains a missing session (401) without exposing details", async () => {
    mockFetch(() => json({ detail: "x" }, 401));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Sesión no válida");
  });

  it("explains a denied user (403)", async () => {
    mockFetch(() => json({ detail: "x" }, 403));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Acceso denegado");
  });

  it("runs the database round trip", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith("/me")) return json({ identifier: "a", email: null, role: "administrator" });
      if (init?.method === "POST" && url.endsWith("/check"))
        return json({
          status: "ok",
          database: "ok",
          check_id: "1",
          checks_total: 3,
          recorded_at: "2026-11-20T18:00:00+01:00",
        });
      return json({}, 404);
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Comprobar base de datos" }));
    expect(await screen.findByText(/Comprobaciones: 3/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/technical/check",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("uploads a technical file directly to storage with the temporary grant", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith("/me")) return json({ identifier: "a", email: null, role: "administrator" });
      if (url.endsWith("/upload-grants"))
        return json({
          upload_id: "abc123",
          url: "http://127.0.0.1:10000/devstoreaccount1/uploads/technical/abc123?sp=c&sig=x",
          method: "PUT",
          headers: { "x-ms-blob-type": "BlockBlob", "If-None-Match": "*" },
          expires_at: "2026-11-20T18:15:00+00:00",
        });
      if (url.includes("blob") || url.includes("127.0.0.1:10000")) {
        expect(init?.method).toBe("PUT");
        return new Response(null, { status: 201 });
      }
      if (url.endsWith("/uploads/abc123"))
        return json({ upload_id: "abc123", container: "uploads", size: 5 });
      return json({}, 404);
    });
    render(<App />);
    const input = screen.getByLabelText("Archivo técnico");
    fireEvent.change(input, {
      target: { files: [new File(["hello"], "technical.txt", { type: "text/plain" })] },
    });
    expect(await screen.findByText(/uploads/)).toBeInTheDocument();
    const calls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes("127.0.0.1:10000"))).toBe(true);
  });

  it("reports a storage rejection", async () => {
    mockFetch((url) => {
      if (url.endsWith("/me")) return json({ identifier: "a", email: null, role: "administrator" });
      if (url.endsWith("/upload-grants"))
        return json({
          upload_id: "x",
          url: "http://storage.test/c/x?sig=1",
          method: "PUT",
          headers: {},
          expires_at: "",
        });
      return new Response(null, { status: 403 });
    });
    render(<App />);
    await waitFor(() => screen.getByLabelText("Archivo técnico"));
    fireEvent.change(screen.getByLabelText("Archivo técnico"), {
      target: { files: [new File(["x"], "t.txt")] },
    });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("El almacenamiento rechazó el archivo");
    expect(alert).not.toHaveTextContent("Acceso denegado");
  });

  it("shows a generic message for an unexpected API failure", async () => {
    mockFetch((url) =>
      url.endsWith("/me")
        ? json({ identifier: "a", email: null, role: "administrator" })
        : json({}, 500),
    );
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Comprobar base de datos" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo completar");
  });
});
