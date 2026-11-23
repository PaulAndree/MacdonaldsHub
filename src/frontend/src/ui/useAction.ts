import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { ApiError } from "../api/client";

/**
 * A change the user triggers (confirm, discard, pause...). It never fails silently: `error` holds
 * what went wrong, to show with <ErrorState mutation error={error} />. A refusal for lack of
 * permission (403) or session (401) also refreshes the session, because the role the interface
 * assumed may no longer be true (for example the identity was removed from the allowlist).
 */
export function useAction<Variables, Result>(action: (variables: Variables) => Promise<Result>) {
  const queryClient = useQueryClient();
  // A second request while one is running is ignored, even before the screen has re-rendered.
  const running = useRef(false);
  const mutation = useMutation<Result, unknown, Variables>({
    mutationFn: action,
    retry: false,
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        void queryClient.invalidateQueries({ queryKey: ["session"] });
      }
    },
  });
  const run = (variables: Variables, options?: { onSuccess?: (data: Result) => void }) => {
    if (running.current) return;
    running.current = true;
    mutation.mutate(variables, {
      onSuccess: options?.onSuccess,
      onSettled: () => {
        running.current = false;
      },
    });
  };
  return {
    run,
    runAsync: mutation.mutateAsync,
    pending: mutation.isPending,
    error: mutation.error,
    succeeded: mutation.isSuccess,
    data: mutation.data,
    reset: mutation.reset,
  };
}
