import type { Permission } from "../../app/areas";
import { useSession } from "./useSession";

/** Whether the signed-in user's role allows an action. Hiding an action is only a convenience: the API decides. */
export function usePermission(permission: Permission): boolean {
  const session = useSession();
  return session.data?.permissions.includes(permission) ?? false;
}
