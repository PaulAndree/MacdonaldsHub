import { describe, expect, it } from "vitest";
import { formatTimestamp } from "./format";

describe("formatTimestamp (RNF-13)", () => {
  it("shows a UTC instant in Madrid time: UTC+1 in winter", () => {
    expect(formatTimestamp("2026-11-22T09:30:00Z")).toBe("2026-11-22 10:30");
  });

  it("shows UTC+2 in summer", () => {
    expect(formatTimestamp("2026-07-15T09:30:00Z")).toBe("2026-07-15 11:30");
  });

  it("moves to the next day when Madrid is already past midnight", () => {
    expect(formatTimestamp("2026-11-22T23:30:00Z")).toBe("2026-11-23 00:30");
  });
});
