import type { components } from "../api/schema";

type Permission = components["schemas"]["Permission"];

/**
 * The permission each operation needs. This only simulates the API's role check so the interface can
 * show the denial of UI-10; the real authorization is the backend's (change 2).
 * `null` means any signed-in user.
 */
export const requiredPermission: Record<string, Permission | null> = {
  getSession: null,
  discardUnconfirmedBatches: null,
  createBatch: "import",
  getPendingBatch: "import",
  getBatch: "import",
  completeUpload: "import",
  listBatchRows: "import",
  downloadExcludedReport: "import",
  getConfirmationSummary: "import",
  discardBatch: "import",
  confirmBatch: "confirm",
  listIncidents: "incidents_read",
  listBranchOptions: "incidents_read",
  exportIncidents: "incidents_read",
  getIncident: "incidents_read",
  checkManualIncident: "incidents_write",
  createManualIncident: "incidents_write",
  claimGlovoIncident: "incidents_write",
  recordIncidentResult: "incidents_write",
  correctIncidentResult: "incidents_write",
  getMetrics: "metrics_read",
  getEmailQueue: "queue_control",
  pauseEmailQueue: "queue_control",
  resumeEmailQueue: "queue_control",
};
