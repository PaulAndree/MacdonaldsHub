import { describe, expect, it } from "vitest";
import { amountToInput, parseAmountInput } from "./amount";

describe("amount typed by a person", () => {
  it.each([
    ["12,50", "12.50"],
    ["12.50", "12.50"],
    ["0,1234", "0.1234"],
    ["8", "8"],
    ["-3,00", "-3.00"],
    ["  7,5  ", "7.5"],
    ["0", "0"],
    ["0,00", "0.00"],
  ])("%s is sent as %s, with the same digits", (typed, sent) => {
    expect(parseAmountInput(typed)).toEqual({ ok: true, value: sent });
  });

  it("an empty box is absent, which is not zero", () => {
    expect(parseAmountInput("")).toEqual({ ok: true, value: null });
    expect(parseAmountInput("   ")).toEqual({ ok: true, value: null });
    expect(parseAmountInput("0")).not.toEqual(parseAmountInput(""));
  });

  it.each(["abc", "12,50 €", "12,5€", "1.234,50", "1,2,3", "--3", "12 50", "€12", ",5", "5,"])("%s is rejected", (typed) => {
    expect(parseAmountInput(typed)).toEqual({ ok: false });
  });

  it("puts a value back in the box with a decimal comma and the same digits", () => {
    expect(amountToInput("12.00")).toBe("12,00");
    expect(amountToInput("0.1234")).toBe("0,1234");
    expect(amountToInput(null)).toBe("");
  });

  it("what is shown in the box parses back to the value it came from", () => {
    for (const value of ["12.00", "0.1234", "-3.5", "100"]) {
      expect(parseAmountInput(amountToInput(value))).toEqual({ ok: true, value });
    }
  });
});
