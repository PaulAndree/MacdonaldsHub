import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { beforeAll, describe, expect, it } from "vitest";
import { loadContract } from "./load";

let ajv: Ajv2020;

function validator(name: string) {
  const v = ajv.getSchema(`contract#/components/schemas/${name}`);
  if (!v) throw new Error(`schema ${name} not found`);
  return v;
}

const core = {
  provider: "uber eats",
  orderId: "AB-1029x",
  incidentDate: "2026-10-12",
  incidentTime: "20:22",
  branch: "centro",
  claimAmount: "12.50",
  providerCosts: null,
  total: null,
  description: null,
};

beforeAll(() => {
  ajv = new Ajv2020({ strict: false, allErrors: true });
  addFormats(ajv);
  ajv.addSchema(loadContract(), "contract");
});

describe("shared contract schemas (RNF-13)", () => {
  it("keeps an amount with more than two decimals as the same string", () => {
    const amount = validator("Amount");
    expect(amount("0.1234")).toBe(true);
    expect(amount("-3.00")).toBe(true);
  });

  it("rejects amounts sent as JSON numbers, so they cannot lose precision", () => {
    const amount = validator("Amount");
    expect(amount(0.1234)).toBe(false);
    expect(amount(0)).toBe(false);
    const optional = validator("OptionalAmount");
    expect(optional(12.5)).toBe(false);
  });

  it("represents an absent amount as null and never as zero", () => {
    const optional = validator("OptionalAmount");
    expect(optional(null)).toBe(true);
    expect(optional("0")).toBe(true); // an explicit zero is a real value, distinct from absent
    const incident = validator("IncidentCore");
    expect(incident(core)).toBe(true);
    // a field cannot simply be omitted: absence must be explicit
    const { total, ...withoutTotal } = core;
    void total;
    expect(incident(withoutTotal)).toBe(false);
  });

  it("allows an incident without time and never requires 00:00", () => {
    const incident = validator("IncidentCore");
    expect(incident({ ...core, incidentTime: null })).toBe(true);
    expect(incident({ ...core, incidentTime: "24:00" })).toBe(false);
    expect(incident({ ...core, incidentDate: "12/10/2026" })).toBe(false);
  });

  it("accepts only lowercase providers", () => {
    const incident = validator("IncidentCore");
    expect(incident({ ...core, provider: "Uber Eats" })).toBe(false);
    expect(incident({ ...core, provider: "glovo" })).toBe(true);
  });

  it("lists send_error as a distinct incident state", () => {
    const schemas = (loadContract().components as { schemas: Record<string, { enum: string[] }> }).schemas;
    const states = schemas.IncidentStatus.enum;
    expect(states).toContain("send_error");
    expect(states).toContain("pending_send");
  });
});
