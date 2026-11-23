import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ApiError } from "../api/client";
import BatchScreen from "../features/batches/BatchScreen";
import ImportScreen from "../features/batches/ImportScreen";
import PendingBatchNotice from "../features/batches/PendingBatchNotice";
import { usePendingBatch } from "../features/batches/queries";
import IncidentDetailScreen from "../features/incidents/IncidentDetailScreen";
import IncidentsScreen from "../features/incidents/IncidentsScreen";
import ManualEntryScreen from "../features/incidents/ManualEntryScreen";
import MetricsScreen from "../features/metrics/MetricsScreen";
import QueueScreen from "../features/queue/QueueScreen";
import type { ExampleUi } from "../example/ui";
import { NoSessionScreen, NotAuthorizedScreen } from "../features/session/AccessScreens";
import RequirePermission from "../features/session/RequirePermission";
import { useSession } from "../features/session/useSession";
import { ErrorState, LoadingState } from "../ui/StateViews";
import type { Area, Permission } from "./areas";
import EnvironmentBanner from "./EnvironmentBanner";
import Layout from "./Layout";
import SessionBadge from "./SessionBadge";
import NotFound from "./NotFound";

interface AppRoutesProps {
  areas: Area[];
  /** Present only in the example build; the standard build never passes it. */
  exampleUi?: ExampleUi;
}

/**
 * The common frame of every screen: banners, navigation, session area and footer.
 * It also decides what the user sees before and without a valid session.
 */
function Shell({ areas, exampleUi }: AppRoutesProps) {
  const session = useSession();
  const { pathname } = useLocation();
  const status = session.error instanceof ApiError ? session.error.status : null;
  const canImport = session.data?.permissions.includes("import") ?? false;
  const pending = usePendingBatch(canImport);

  let visible: Area[] = [];
  let gate: ReactNode = null;
  if (session.data) {
    const granted = new Set<Permission>(session.data.permissions);
    visible = areas.filter((area) => area.permission === null || granted.has(area.permission));
  } else if (session.isPending) {
    gate = <LoadingState />;
  } else if (status === 401) {
    gate = <NoSessionScreen />;
  } else if (status === 403) {
    gate = <NotAuthorizedScreen />;
  } else {
    // The session could not be read (for example the operation is not available yet): nothing else
    // can be shown, because every screen depends on knowing who the user is.
    gate = <ErrorState error={session.error} onRetry={() => void session.refetch()} />;
  }

  const banners: ReactNode = (
    <>
      {exampleUi?.banner}
      {session.data?.environment === "test" && <EnvironmentBanner />}
    </>
  );
  // A batch the user has not confirmed is offered back on every screen except those that already
  // handle it. It does not expire (RF-17).
  const handlesPending = pathname.startsWith("/lotes/") || pathname.startsWith("/importar");
  const notice = pending.data && !handlesPending && !gate ? <PendingBatchNotice batch={pending.data} /> : null;

  return (
    <Layout
      areas={visible}
      banners={banners}
      session={<SessionBadge />}
      footer={exampleUi?.footer}
      gate={gate}
      notice={notice}
    />
  );
}

/** A screen only for roles with this permission; others see a denial. */
function guarded(permission: Permission, element: ReactNode) {
  return <RequirePermission permission={permission}>{element}</RequirePermission>;
}

/** Every route of the interface. Each area replaces its stub in its own task. */
export default function AppRoutes({ areas, exampleUi }: AppRoutesProps) {
  return (
    <Routes>
      <Route element={<Shell areas={areas} exampleUi={exampleUi} />}>
        <Route index element={<Navigate to="/importar" replace />} />
        <Route path="importar" element={guarded("import", <ImportScreen />)} />
        <Route path="lotes/:batchId" element={guarded("import", <BatchScreen />)} />
        <Route path="incidencias" element={guarded("incidents_read", <IncidentsScreen />)} />
        <Route path="incidencias/nueva" element={guarded("incidents_write", <ManualEntryScreen />)} />
        <Route path="incidencias/:incidentId" element={guarded("incidents_read", <IncidentDetailScreen />)} />
        <Route path="panel" element={guarded("metrics_read", <MetricsScreen />)} />
        <Route path="correo" element={guarded("queue_control", <QueueScreen />)} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
