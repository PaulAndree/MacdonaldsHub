import { NetworkError, StorageError } from "./client";
import type { components } from "./schema";

type UploadGrant = components["schemas"]["UploadGrant"];

/**
 * Uploads a file straight to storage with the temporary create-only permission the API issued.
 * XMLHttpRequest is used because `fetch` cannot report upload progress.
 */
export function putFile(grant: UploadGrant, file: File, onProgress: (fraction: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(grant.method, grant.url);
    for (const [name, value] of Object.entries(grant.headers)) request.setRequestHeader(name, value);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
    };
    request.onload = () =>
      request.status >= 200 && request.status < 300 ? resolve() : reject(new StorageError(request.status));
    request.onerror = () => reject(new NetworkError());
    request.send(file);
  });
}
