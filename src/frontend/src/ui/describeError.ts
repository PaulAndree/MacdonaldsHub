import { ApiError, NetworkError, StorageError } from "../api/client";
import { es } from "../i18n/es";

/**
 * Turns an error into a message for the user.
 * It never claims an outcome it cannot know: after a network failure on a change, the message says the
 * outcome is unknown instead of saying the change did or did not happen.
 */
export function describeError(error: unknown, options: { mutation?: boolean } = {}): string {
  if (error instanceof StorageError) return es.errors.storageRejected;
  if (error instanceof NetworkError) {
    return options.mutation ? es.errors.outcomeUnknown : es.errors.readFailed;
  }
  if (error instanceof ApiError) {
    if (error.status === 401) return es.errors.noSession;
    if (error.status === 403) return options.mutation ? es.errors.forbiddenAction : es.errors.forbidden;
    if (error.status === 404) return es.errors.notFound;
    // The server explained a refusal (409, 422): that message is meant for the user.
    if (error.status >= 400 && error.status < 500 && error.message && !error.message.startsWith("HTTP ")) {
      return error.message;
    }
    return options.mutation ? es.errors.generic : es.errors.readFailed;
  }
  return es.errors.generic;
}
