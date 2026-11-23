"""Worker entrypoint: `python -m app.worker.main`."""

import signal
import threading

from opentelemetry import trace

from app.adapters.db.advisory_lock import AdvisoryLock
from app.adapters.db.cleanup import SqlCleanupRepository
from app.adapters.db.engine import make_engine
from app.adapters.db.original_copy import SqlOriginalCopyRepository
from app.adapters.db.preparation import SqlPreparationRepository
from app.adapters.registry import default_registry
from app.composition import Container
from app.services.cleanup import CleanupService
from app.services.original_copy import OriginalCopyService
from app.services.preparation import PreparationService
from app.settings import StartupError, load_settings_or_exit
from app.startup_checks import require_catalog
from app.worker.health_server import make_health_server, serve_in_background
from app.worker.healthcheck import DEFAULT_PATH
from app.worker.loop import Worker

INTERVAL_SECONDS = 5.0


def main() -> None:
    settings = load_settings_or_exit()
    container = Container(settings, default_registry())
    container.telemetry().configure("delivery-hub-worker")
    engine = make_engine(settings.database_url.get_secret_value(), settings.database_auth)
    try:
        require_catalog(engine, settings)
    except StartupError as exc:
        raise SystemExit(f"Startup refused: {exc}") from None
    preparation = PreparationService(SqlPreparationRepository(engine), container.storage())

    copier = OriginalCopyService(SqlOriginalCopyRepository(engine), container.storage())

    cleaner = CleanupService(SqlCleanupRepository(engine), container.storage())

    def prepare() -> None:
        preparation.process_pending()
        copier.process_pending()
        cleaner.process_pending()

    worker = Worker(
        AdvisoryLock(engine),
        trace.get_tracer("delivery-hub.worker"),
        DEFAULT_PATH,
        work=prepare if settings.imports_enabled else None,
    )

    health = make_health_server(DEFAULT_PATH)
    serve_in_background(health)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        worker.run(stop, INTERVAL_SECONDS)
    finally:
        health.shutdown()


if __name__ == "__main__":
    main()
