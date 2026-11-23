import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./client";

/** A refused request (4xx) will not change on retry; only transient failures are retried. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false;
  return failureCount < 1;
}

export function createQueryClient(options: { retryDelay?: number } = {}): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        retryDelay: options.retryDelay,
        refetchOnWindowFocus: false,
        staleTime: 0,
      },
      mutations: { retry: false },
    },
  });
}
