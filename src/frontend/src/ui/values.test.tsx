import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { es } from "../i18n/es";
import {
  AmountText,
  BranchText,
  IncidentDateText,
  OptionalText,
  Timestamp,
  formatAmount,
  formatRate,
  providerName,
} from "./values";

const text = (ui: React.ReactElement) => render(ui).container.textContent;

describe("amounts keep their value (RNF-13, UI-01)", () => {
  it.each([
    ["0.1234", "0,1234 €"],
    ["12.50", "12,50 €"],
    ["12.5", "12,5 €"],
    ["-3.00", "-3,00 €"],
    ["0", "0 €"],
    ["0.00", "0,00 €"],
    ["1234567.5", "1.234.567,5 €"],
    ["100", "100 €"],
    ["0.10000000000000000001", "0,10000000000000000001 €"],
  ])("%s is shown as %s, never rounded or recomputed", (value, shown) => {
    expect(formatAmount(value)).toBe(shown);
    expect(text(<AmountText value={value} />)).toBe(shown);
  });

  it("does not round a value with more than two decimals to two", () => {
    expect(text(<AmountText value="0.1234" />)).not.toBe("0,12 €");
    expect(text(<AmountText value="2.999" />)).toBe("2,999 €");
  });

  it("keeps the sign as received, including zero and negatives", () => {
    expect(text(<AmountText value="-12.5" />)).toBe("-12,5 €");
    expect(text(<AmountText value="0" />)).toBe("0 €");
  });

  it("shows an absent amount as unknown and never as zero", () => {
    const view = render(<AmountText value={null} />);
    expect(view.container).toHaveTextContent(es.values.unknownAmount);
    expect(view.container.textContent).not.toMatch(/0/);
    expect(view.container.textContent).not.toContain("€");
    expect(view.container.querySelector(".unknown")).not.toBeNull();
  });

  it("leaves text that is not a plain decimal exactly as it came", () => {
    expect(formatAmount("12,50 €")).toBe("12,50 €");
    expect(formatAmount("abc")).toBe("abc");
  });
});

describe("incident date and time (RNF-13)", () => {
  it("shows the time only when the source had one", () => {
    expect(text(<IncidentDateText date="2026-10-12" time="20:22" />)).toBe("2026-10-12 20:22");
  });

  it("shows only the date, and never invents 00:00, when there is no time", () => {
    const shown = text(<IncidentDateText date="2026-10-12" time={null} />);
    expect(shown).toBe("2026-10-12");
    expect(shown).not.toContain("00:00");
  });

  it("keeps a real midnight time from the source", () => {
    expect(text(<IncidentDateText date="2026-10-12" time="00:00" />)).toBe("2026-10-12 00:00");
  });

  it("keeps a date that is not in the expected format, as read from the file", () => {
    expect(text(<IncidentDateText date="12/10/2026" time={null} />)).toBe("12/10/2026");
  });

  it("marks the time as Madrid time for assistive technology and hover", () => {
    render(<IncidentDateText date="2026-10-12" time="20:22" />);
    expect(screen.getByTitle(es.values.madridTime)).toHaveTextContent("2026-10-12 20:22");
  });
});

describe("branch and other optional values", () => {
  it("a missing branch reads Sin sucursal", () => {
    expect(text(<BranchText branch={null} />)).toBe(es.values.noBranch);
    expect(text(<BranchText branch="centro" />)).toBe("centro");
  });

  it("an empty optional text says so", () => {
    expect(text(<OptionalText value={null} empty={es.values.noDescription} />)).toBe(es.values.noDescription);
    expect(text(<OptionalText value="Falta una bebida" />)).toBe("Falta una bebida");
  });
});

describe("timestamps and provider names", () => {
  it("shows a system timestamp in Madrid time with the UTC instant in the markup", () => {
    const { container } = render(<Timestamp value="2026-11-22T09:30:00Z" />);
    expect(container).toHaveTextContent("2026-11-22 10:30");
    expect(container.querySelector("time")?.getAttribute("datetime")).toBe("2026-11-22T09:30:00Z");
  });

  it("names providers for display and leaves unknown ones as they are", () => {
    expect(providerName("uber eats")).toBe("Uber Eats");
    expect(providerName("just eat")).toBe("Just Eat");
    expect(providerName("glovo")).toBe("Glovo");
    expect(providerName("otro")).toBe("otro");
    expect(providerName(null)).toBe(es.values.unknown);
  });
});

describe("rates keep their digits", () => {
  it.each([
    ["0.3692", "36,92 %"],
    ["0.1920", "19,20 %"],
    ["0.5", "50 %"],
    ["1", "100 %"],
    ["0.12345", "12,345 %"],
    ["0.0500", "5,00 %"],
    ["0", "0 %"],
  ])("%s is shown as %s", (rate, shown) => {
    expect(formatRate(rate)).toBe(shown);
  });

  it("leaves text that is not a plain rate as it came", () => {
    expect(formatRate("abc")).toBe("abc");
  });
});
