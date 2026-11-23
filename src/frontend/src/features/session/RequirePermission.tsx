import type { ReactNode } from "react";
import type { Permission } from "../../app/areas";
import { DeniedState } from "../../ui/StateViews";
import { useSession } from "./useSession";

/**
 * Shows a denial instead of an area the user's role does not allow, for someone who types the address.
 * This is a convenience: the API still authorizes every operation. While the session is unknown the
 * frame decides what to show, so this renders its children.
 */
export default function RequirePermission({ permission, children }: { permission: Permission; children: ReactNode }) {
  const session = useSession();
  if (session.data && !session.data.permissions.includes(permission)) return <DeniedState />;
  return <>{children}</>;
}
