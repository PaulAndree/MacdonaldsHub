import { describe, expect, it } from "vitest";
import { daysBetween, ratio, sumDecimals } from "./decimal";

describe("exact decimal arithmetic", () => {
  it("adds without the errors of floating point", () => {
    expect(0.1 + 0.2).not.toBe(0.3); // the problem this avoids
    expect(sumDecimals(["0.1", "0.2"])).toBe("0.3");
    expect(sumDecimals(["12.50", "20.00"])).toBe("32.50");
    expect(sumDecimals(["0.1234", "1"])).toBe("1.1234");
  });

  it("keeps the most precise number of decimals and the sign", () => {
    expect(sumDecimals(["1", "2"])).toBe("3");
    expect(sumDecimals(["-3.00", "1.25"])).toBe("-1.75");
    expect(sumDecimals(["0.05", "-0.05"])).toBe("0.00");
  });

  it("an empty list has no sum, which is not zero", () => {
    expect(sumDecimals([])).toBeNull();
  });

  it("is exact for very large values", () => {
    expect(sumDecimals(["99999999999999999999.99", "0.01"])).toBe("100000000000000000000.00");
  });

  it("divides to a fixed number of decimals, rounding half up", () => {
    expect(ratio("12.00", "32.50")).toBe("0.3692");
    expect(ratio("8.00", "10.00")).toBe("0.8000");
    expect(ratio("1", "3")).toBe("0.3333");
    expect(ratio("2", "3")).toBe("0.6667");
    expect(ratio("1", "8", 2)).toBe("0.13");
  });

  it("cannot divide by zero", () => {
    expect(ratio("5.00", "0.00")).toBeNull();
  });

  it("counts whole days between ISO dates", () => {
    expect(daysBetween("2026-11-20", "2026-11-22")).toBe(2);
    expect(daysBetween("2026-10-30", "2026-11-22")).toBe(23);
    expect(daysBetween("2026-02-28", "2026-03-01")).toBe(1);
  });
});
