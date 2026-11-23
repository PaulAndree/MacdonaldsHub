import { es } from "../../i18n/es";
import type { HistoryEntry, Incident } from "./types";

const t = es.incidents.email;

/**
 * What the email of an incident is doing. There is never an action here: each email has one attempt and
 * there is no retry, resend or cancel, so a failed one is explained, not offered again.
 */
export default function EmailStateNotice({ incident, history }: { incident: Incident; history: HistoryEntry[] }) {
  if (incident.status === "send_error") {
    const reason = [...history].reverse().find((entry) => entry.kind === "email_result" && entry.reason)?.reason;
    return (
      <div className="notice notice--danger" role="note">
        <h3 style={{ marginTop: 0 }}>{t.errorTitle}</h3>
        <p>{reason ? t.errorReason(reason) : t.errorNoReason}</p>
        <p>{t.errorNoRetry}</p>
      </div>
    );
  }
  if (incident.status === "pending_send") {
    return (
      <div className="notice" role="note">
        <h3 style={{ marginTop: 0 }}>{t.pendingTitle}</h3>
        <p>{t.pendingText}</p>
      </div>
    );
  }
  return null;
}
