export type Me = { identifier: string; email: string | null; role: string };
export type CheckResult = {
  status: string;
  database: string;
  check_id: string;
  checks_total: number;
  recorded_at: string;
};
export type UploadGrant = {
  upload_id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  expires_at: string;
};
export type UploadInfo = { upload_id: string; container: string; size: number };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export class StorageError extends Error {
  constructor(public status: number) {
    super(`Storage rejected the upload (HTTP ${status})`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", ...init });
  if (!response.ok) {
    throw new ApiError(response.status, `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const getMe = () => request<Me>("/api/technical/me");
export const runCheck = () => request<CheckResult>("/api/technical/check", { method: "POST" });
export const getUpload = (id: string) => request<UploadInfo>(`/api/technical/uploads/${id}`);
const requestGrant = () =>
  request<UploadGrant>("/api/technical/upload-grants", { method: "POST" });

/** Direct browser -> Blob upload with the temporary create-only permission from the API. */
export async function uploadTechnicalFile(file: File): Promise<UploadInfo> {
  const grant = await requestGrant();
  const put = await fetch(grant.url, { method: grant.method, headers: grant.headers, body: file });
  if (!put.ok) {
    throw new StorageError(put.status);
  }
  return getUpload(grant.upload_id);
}
