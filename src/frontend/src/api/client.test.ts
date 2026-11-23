import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError, api } from "./client";

function respond(status: number, body?: unknown) {
  const fn = vi.fn(async () =>
    body === undefined
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("returns the parsed body of a successful read and sends the session cookie", async () => {
    const fn = respond(200, { a: 1 });
    await expect(api.get("/api/session")).resolves.toEqual({ a: 1 });
    expect(fn).toHaveBeenCalledWith("/api/session", expect.objectContaining({ credentials: "same-origin" }));
  });

  it("drops empty query values and keeps the others", async () => {
    const fn = respond(200, {});
    await api.get("/api/incidents", { provider: "glovo", branch: "", status: undefined, page: 2 });
    const calls = fn.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0]?.[0]).toBe("/api/incidents?provider=glovo&page=2");
  });

  it("sends a JSON body on a change", async () => {
    const fn = respond(201, { id: "x" });
    await api.post("/api/batches", { fileName: "a.xlsx" });
    const calls = fn.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0]?.[1].method).toBe("POST");
    expect(calls[0]?.[1].body).toBe('{"fileName":"a.xlsx"}');
  });

  it("returns undefined for 204", async () => {
    respond(204);
    await expect(api.delete("/api/admin/authorizations/auth-2")).resolves.toBeUndefined();
  });

  it("raises an ApiError carrying the code, message and details the server sent", async () => {
    respond(409, { code: "unconfirmed_batch_exists", message: "Ya tiene un lote.", details: { batchId: "l-6" } });
    const error = await api.post("/api/batches", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "unconfirmed_batch_exists", details: { batchId: "l-6" } });
  });

  it("still raises an ApiError when the error body is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>", { status: 502 })));
    await expect(api.get("/api/session")).rejects.toMatchObject({ status: 502, code: "http_502" });
  });

  it("raises a NetworkError when no answer arrives", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    await expect(api.post("/api/batches/x/confirm", {})).rejects.toBeInstanceOf(NetworkError);
  });
});
