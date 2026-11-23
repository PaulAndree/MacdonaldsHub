import { describe, expect, it } from "vitest";
import { ApiError, NetworkError } from "../api/client";
import { es } from "../i18n/es";
import { describeError } from "./describeError";

describe("describeError", () => {
  it("explains a missing session and a denial", () => {
    expect(describeError(new ApiError(401, "not_authenticated", "x"))).toBe(es.errors.noSession);
    expect(describeError(new ApiError(403, "not_authorized", "x"))).toBe(es.errors.forbidden);
  });

  it("uses the server's own message when it explains a refusal", () => {
    const error = new ApiError(409, "batch_discarded", "El lote fue descartado y ya no se puede confirmar.");
    expect(describeError(error, { mutation: true })).toBe(error.message);
  });

  it("does not show a raw HTTP status to the user", () => {
    expect(describeError(new ApiError(500, "http_500", "HTTP 500"))).toBe(es.errors.readFailed);
    expect(describeError(new ApiError(500, "http_500", "HTTP 500"), { mutation: true })).toBe(es.errors.generic);
  });

  it("says the outcome is unknown after a network failure on a change", () => {
    const message = describeError(new NetworkError(), { mutation: true });
    expect(message).toBe(es.errors.outcomeUnknown);
    expect(message).toMatch(/no sabemos si/i);
  });

  it("never claims an outcome it cannot know (RF-09)", () => {
    const claims = /no se (ha )?(creado|guardado|confirmado|enviado)|se (ha )?(creado|guardado|confirmado) correctamente/i;
    for (const mutation of [true, false]) {
      for (const error of [new NetworkError(), new ApiError(500, "http_500", "HTTP 500"), new Error("boom")]) {
        expect(describeError(error, { mutation })).not.toMatch(claims);
      }
    }
  });

  it("falls back to a generic message for an unknown error", () => {
    expect(describeError(new Error("boom"))).toBe(es.errors.generic);
  });
});
