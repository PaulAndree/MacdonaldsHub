import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type Session = components["schemas"]["Session"];

/** The signed-in user's identity, role, environment and permissions. */
export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: () => api.get<Session>("/api/session"),
    retry: false,
    staleTime: 60_000,
    // Several components read the session. Mounting another one must not retry a failed read, or a
    // missing operation would be requested in a loop; the user retries explicitly.
    retryOnMount: false,
  });
}
