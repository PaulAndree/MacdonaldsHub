import { es } from "../../i18n/es";
import type { IncidentStatus } from "./types";

const STYLE: Record<IncidentStatus, string> = {
  imported_no_email: "pill--wait",
  pending_send: "pill--review",
  claimed: "pill--wait",
  send_error: "pill--new",
  resolved: "pill--ok",
  rejected: "pill--new",
};

export default function StatusPill({ status }: { status: IncidentStatus }) {
  return <span className={`pill ${STYLE[status]}`}>{es.incidents.status[status]}</span>;
}
