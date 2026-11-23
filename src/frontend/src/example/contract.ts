import contractJson from "./contract.json";

export type Method = "get" | "post" | "put" | "delete";

export interface ExampleResponse {
  name: string;
  status: number;
  value: unknown;
}

export interface Operation {
  id: string;
  method: Method;
  /** Path as written in the contract, for example `/api/batches/{batchId}`. */
  path: string;
  /** Same path as a request-matching pattern, for example `/api/batches/:batchId`. */
  pattern: string;
  /** Named examples by status code. A status with no JSON body (204, a file) has none. */
  examples: Map<number, ExampleResponse[]>;
  /** Statuses the operation can answer with. */
  statuses: number[];
  /** True when the success response is a file download. */
  binary: boolean;
}

type Json = Record<string, unknown>;
const contract = contractJson as unknown as Json;
const METHODS: Method[] = ["get", "post", "put", "delete"];

function resolveRef(node: unknown): Json {
  const obj = node as Json;
  if (typeof obj?.$ref === "string") {
    const parts = obj.$ref.replace(/^#\//, "").split("/");
    let current: unknown = contract;
    for (const part of parts) current = (current as Json)[part];
    return current as Json;
  }
  return obj;
}

function build(): Operation[] {
  const operations: Operation[] = [];
  const paths = contract.paths as Record<string, Json>;
  for (const [path, item] of Object.entries(paths)) {
    for (const method of METHODS) {
      const operation = item[method] as Json | undefined;
      if (!operation) continue;
      const examples = new Map<number, ExampleResponse[]>();
      const statuses: number[] = [];
      let binary = false;
      for (const [code, rawResponse] of Object.entries(operation.responses as Json)) {
        const status = Number(code);
        statuses.push(status);
        const response = resolveRef(rawResponse);
        const content = (response.content ?? {}) as Record<string, Json>;
        if (status < 300 && Object.keys(content).some((type) => !type.includes("json"))) binary = true;
        const media = content["application/json"];
        const named = (media?.examples ?? {}) as Record<string, Json>;
        const list = Object.entries(named).map(([name, example]) => ({
          name,
          status,
          value: example.value,
        }));
        if (list.length > 0) examples.set(status, list);
      }
      operations.push({
        id: operation.operationId as string,
        method,
        path,
        pattern: path.replace(/\{(\w+)\}/g, ":$1"),
        examples,
        statuses,
        binary,
      });
    }
  }
  // Literal paths first, so `/api/batches/pending` is not captured by `/api/batches/:batchId`.
  return operations.sort(
    (a, b) => (a.pattern.match(/:/g)?.length ?? 0) - (b.pattern.match(/:/g)?.length ?? 0),
  );
}

export const operations: Operation[] = build();

export function operation(id: string): Operation {
  const found = operations.find((op) => op.id === id);
  if (!found) throw new Error(`Unknown operation ${id}`);
  return found;
}

/** A named example of an operation response; throws when the contract has no such example. */
export function example<T = unknown>(operationId: string, status: number, name?: string): T {
  const list = operation(operationId).examples.get(status);
  const found = name ? list?.find((e) => e.name === name) : list?.[0];
  if (!found) throw new Error(`No example ${name ?? "(first)"} for ${operationId} ${status}`);
  return structuredClone(found.value) as T;
}

/** The success status of an operation: the lowest 2xx. */
export function successStatus(op: Operation): number {
  return Math.min(...op.statuses.filter((s) => s >= 200 && s < 300));
}
