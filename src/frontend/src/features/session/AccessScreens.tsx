import { es } from "../../i18n/es";
import PageHeader from "../../ui/PageHeader";

/** The session is missing or expired. Reloading restarts the Google sign-in through Easy Auth. */
export function NoSessionScreen() {
  return (
    <>
      <PageHeader title={es.access.noSessionTitle} />
      <div className="notice notice--warning" role="alert">
        <p>{es.errors.noSession}</p>
        <p>{es.access.noSessionHelp}</p>
        <button type="button" onClick={() => window.location.reload()}>
          {es.access.reload}
        </button>
      </div>
    </>
  );
}

/** Google authenticated the user, but the allowlist does not authorize them. */
export function NotAuthorizedScreen() {
  return (
    <>
      <PageHeader title={es.access.notAuthorizedTitle} />
      <div className="notice notice--danger" role="alert">
        <p>{es.access.notAuthorizedText}</p>
        <p>{es.access.notAuthorizedHelp}</p>
      </div>
    </>
  );
}
