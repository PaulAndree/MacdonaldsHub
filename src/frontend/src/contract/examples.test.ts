import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { beforeAll, describe, expect, it } from "vitest";
import { loadContract, type Json } from "./load";

interface Example {
  where: string;
  pointer: string;
  value: unknown;
}

const esc = (key: string) => key.replace(/~/g, "~0").replace(/\//g, "~1");

/** Finds every media-type object (it has a schema and a map of named examples). */
function collectExamples(node: unknown, pointer: string, out: Example[]): void {
  if (Array.isArray(node)) {
    node.forEach((item, i) => collectExamples(item, `${pointer}/${i}`, out));
    return;
  }
  if (node === null || typeof node !== "object") return;
  const obj = node as Json;
  const examples = obj.examples;
  if (obj.schema && examples && typeof examples === "object" && !Array.isArray(examples)) {
    for (const [name, example] of Object.entries(examples as Json)) {
      out.push({
        where: `${pointer} :: ${name}`,
        pointer: `${pointer}/schema`,
        value: (example as Json).value,
      });
    }
  }
  for (const [key, child] of Object.entries(obj)) {
    collectExamples(child, `${pointer}/${esc(key)}`, out);
  }
}

/** Deep copy where every object schema without `additionalProperties` gets `unevaluatedProperties: false`. */
function strictCopy(contract: Json): Json {
  const copy = structuredClone(contract) as Json;
  const schemas = (copy.components as Json).schemas as Json;
  const visit = (node: unknown): void => {
    if (Array.isArray(node)) return node.forEach(visit);
    if (node === null || typeof node !== "object") return;
    const obj = node as Json;
    const isObjectSchema = obj.properties !== undefined || obj.allOf !== undefined;
    if (isObjectSchema && obj.additionalProperties === undefined && obj.unevaluatedProperties === undefined) {
      obj.unevaluatedProperties = false;
    }
    Object.values(obj).forEach(visit);
  };
  visit(schemas);
  return copy;
}

let ajv: Ajv2020;
let examples: Example[];

beforeAll(() => {
  const contract = loadContract();
  examples = [];
  collectExamples(contract, "", examples);
  // Validate against a strict copy: an object schema rejects unknown properties, so a mistyped
  // example key (or a text split by a stray YAML comma) fails instead of passing silently.
  ajv = new Ajv2020({ strict: false, allErrors: true });
  addFormats(ajv);
  ajv.addSchema(strictCopy(contract), "contract");
});

describe("contract examples", () => {
  it("has named examples to validate", () => {
    expect(examples.length).toBeGreaterThan(20);
  });

  it("every named example is valid against the schema of its media type", () => {
    const failures: string[] = [];
    for (const example of examples) {
      const validate = ajv.getSchema(`contract#${example.pointer}`);
      if (!validate) {
        failures.push(`${example.where}: schema not found at ${example.pointer}`);
        continue;
      }
      if (!validate(example.value)) {
        failures.push(`${example.where}: ${ajv.errorsText(validate.errors)}`);
      }
    }
    expect(failures).toEqual([]);
  });

  it("no example carries an amount as a JSON number", () => {
    const offenders: string[] = [];
    // `total` is also a count in paginated responses, so it only counts as an amount
    // inside an incident-like object (one that has an incidentDate).
    const incidentAmountKeys = ["claimAmount", "providerCosts", "total"];
    const walk = (value: unknown, where: string) => {
      if (Array.isArray(value)) return value.forEach((v, i) => walk(v, `${where}[${i}]`));
      if (value && typeof value === "object") {
        const obj = value as Json;
        const incidentLike = "incidentDate" in obj;
        for (const [k, v] of Object.entries(obj)) {
          const isAmount = k === "recoveredAmount" || (incidentLike && incidentAmountKeys.includes(k));
          if (isAmount && typeof v === "number") offenders.push(`${where}.${k}`);
          walk(v, `${where}.${k}`);
        }
      }
    };
    examples.forEach((e) => walk(e.value, e.where));
    expect(offenders).toEqual([]);
  });
});
