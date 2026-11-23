import { es } from "../i18n/es";
import LogoutButton from "../features/batches/LogoutButton";
import { useSession } from "../features/session/useSession";

function initials(name: string): string {
  const parts = name.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** Who is signed in and with which role. Nothing is shown until the session is known. */
export default function SessionBadge() {
  const session = useSession();
  if (!session.data) return null;
  const { email, identifier, role, environment, permissions } = session.data;
  const name = email ?? identifier;
  return (
    <div className="session">
      <span>
        {name}
        <small>
          {es.roles[role]} · {es.access.environment}: {es.environments[environment]}
        </small>
      </span>
      <LogoutButton canImport={permissions.includes("import")} />
      <span className="avatar" aria-hidden="true">
        {initials(name)}
      </span>
    </div>
  );
}
