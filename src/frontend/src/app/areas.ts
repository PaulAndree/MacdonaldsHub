import type { components } from "../api/schema";
import { es } from "../i18n/es";

export type Permission = components["schemas"]["Permission"];

export interface Area {
  id: string;
  path: string;
  label: string;
  /** Permission needed to see the area; `null` means every signed-in user. */
  permission: Permission | null;
}

/** The areas of the interface, in navigation order. Hiding one is a convenience, not security. */
export const areas: Area[] = [
  { id: "import", path: "/importar", label: es.nav.import, permission: "import" },
  { id: "incidents", path: "/incidencias", label: es.nav.incidents, permission: "incidents_read" },
  { id: "manual-entry", path: "/incidencias/nueva", label: es.nav.manualEntry, permission: "incidents_write" },
  { id: "dashboard", path: "/panel", label: es.nav.dashboard, permission: "metrics_read" },
  { id: "queue", path: "/correo", label: es.nav.queue, permission: "queue_control" },
];
