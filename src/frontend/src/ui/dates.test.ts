import { describe, expect, it } from "vitest";
import { isoToDisplay, parseDateField, parseTimeField } from "./dates";

describe("dates are shown and typed as dd/mm/aaaa", () => {
  it("shows an ISO date the Spanish way", () => {
    expect(isoToDisplay("2026-11-21")).toBe("21/11/2026");
    expect(isoToDisplay("2026-01-05")).toBe("05/01/2026");
    expect(isoToDisplay("")).toBe("");
    expect(isoToDisplay(null)).toBe("");
  });

  it("leaves text that is not an ISO date as it is", () => {
    expect(isoToDisplay("12/11/2026")).toBe("12/11/2026");
  });

  it.each([
    ["21/11/2026", "2026-11-21"],
    ["01/02/2026", "2026-02-01"],
    ["1/2/2026", "2026-02-01"],
    ["21-11-2026", "2026-11-21"],
    ["21.11.2026", "2026-11-21"],
    ["  21/11/2026  ", "2026-11-21"],
    ["29/02/2028", "2028-02-29"],
    ["31/12/2026", "2026-12-31"],
  ])("%s is the ISO date %s", (typed, iso) => {
    expect(parseDateField(typed)).toEqual({ ok: true, value: iso });
  });

  it("an empty box is absent, not an error", () => {
    expect(parseDateField("")).toEqual({ ok: true, value: null });
    expect(parseDateField("   ")).toEqual({ ok: true, value: null });
  });

  it.each(["31/02/2026", "29/02/2026", "32/01/2026", "00/01/2026", "10/13/2026", "10/00/2026", "2026-11-21", "21/11/26", "11/21/2026x", "ayer", "21/11", "21/11/1800", "21/11/2200"])(
    "%s is not a date and is rejected, never read as no date",
    (typed) => {
      expect(parseDateField(typed)).toEqual({ ok: false });
    },
  );

  it("is the reverse of showing an ISO date", () => {
    for (const iso of ["2026-11-21", "2028-02-29", "2026-01-01"]) {
      expect(parseDateField(isoToDisplay(iso))).toEqual({ ok: true, value: iso });
    }
  });
});

describe("times are typed as hh:mm in 24 hours", () => {
  it.each([
    ["20:22", "20:22"],
    ["9:05", "09:05"],
    ["00:00", "00:00"],
    ["23:59", "23:59"],
    ["20.22", "20:22"],
  ])("%s is %s", (typed, time) => {
    expect(parseTimeField(typed)).toEqual({ ok: true, value: time });
  });

  it("an empty box is no time: midnight is never assumed", () => {
    expect(parseTimeField("")).toEqual({ ok: true, value: null });
  });

  it.each(["24:00", "12:60", "8pm", "20:2", "1234", "ab:cd", "20:22:10"])("%s is rejected", (typed) => {
    expect(parseTimeField(typed)).toEqual({ ok: false });
  });
});
