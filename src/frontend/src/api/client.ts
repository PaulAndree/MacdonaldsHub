import type { components } from "./schema";

type ErrorBody = components["schemas"]["Error"];

/** The server answered with an error status. The outcome is known: the server refused it. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** No answer was received. For a change (POST, PUT, DELETE) the outcome is unknown. */
export class NetworkError extends Error {
  constructor() {
    super("No response from the server");
    this.name = "NetworkError";
  }
}

/** Storage answered the direct upload with an error: the file was not stored. */
export class StorageError extends Error {
  constructor(public readonly status: number) {
    super(`Storage rejected the upload (HTTP ${status})`);
    this.name = "StorageError";
  }
}

export type Query = Record<string, string | number | undefined | null>;

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

export async function parseError(response: Response): Promise<ApiError> {
  let body: Partial<ErrorBody> = {};
  try {
    body = (await response.json()) as Partial<ErrorBody>;
  } catch {
    // The body is not JSON; the status alone is meaningful.
  }
  return new ApiError(
    response.status,
    body.code ?? `http_${response.status}`,
    body.message ?? `HTTP ${response.status}`,
    body.details,
  );
}

async function send<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  let response: Response;
  try {
    response = await fetch(withQuery(path, query), {
      method,
      credentials: "same-origin",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new NetworkError();
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => send<T>("GET", path, undefined, query),
  post: <T>(path: string, body?: unknown) => send<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => send<T>("PUT", path, body),
  delete: <T>(path: string) => send<T>("DELETE", path),
};
