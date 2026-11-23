"""API entrypoint. Run with: uvicorn app.api.main:create_app --factory --host 0.0.0.0 --port 8000"""

from fastapi import FastAPI, Response
from opentelemetry import trace
from opentelemetry.trace import Tracer
from sqlalchemy import Engine

from app.adapters.db.allowlist import SqlAllowlistRepository
from app.adapters.db.engine import make_engine, ping
from app.adapters.registry import default_registry
from app.api.batches import router as batches_router
from app.api.security import ApiError, AuthMiddleware, api_error_handler
from app.api.session import router as session_router
from app.api.technical import router as technical_router
from app.api.telemetry import TelemetryMiddleware
from app.composition import Container
from app.services.authorization import Authorizer
from app.settings import Settings, StartupError, load_settings_or_exit
from app.startup_checks import require_catalog


def build_app(
    settings: Settings, container: Container, engine: Engine, tracer: Tracer | None = None
) -> FastAPI:
    app = FastAPI(title="Delivery Hub API (platform base)", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.container = container
    app.state.engine = engine

    authorizer = Authorizer(SqlAllowlistRepository(engine), settings.allowlist_identifier)
    app.add_middleware(AuthMiddleware, identity=container.identity(), authorizer=authorizer)
    # Added last so it is outermost: even 401/403 responses carry correlation, actor and result.
    app.add_middleware(TelemetryMiddleware, tracer=tracer or trace.get_tracer("delivery-hub.api"))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness: the process is up. Does not touch dependencies."""
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz(response: Response) -> dict[str, str]:
        """Readiness: PostgreSQL answers."""
        try:
            ok = ping(engine)
        except Exception:
            ok = False
        if not ok:
            response.status_code = 503
            return {"status": "unavailable", "database": "down"}
        return {"status": "ok", "database": "ok"}

    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(session_router)
    app.include_router(batches_router)
    app.include_router(technical_router)
    return app


def create_app() -> FastAPI:
    settings = load_settings_or_exit()
    container = Container(settings, default_registry())
    container.telemetry().configure("delivery-hub-api")
    # Build storage eagerly: containers and CORS are ready, and misconfiguration fails at startup.
    container.storage()
    engine = make_engine(settings.database_url.get_secret_value(), settings.database_auth)
    try:
        require_catalog(engine, settings)
    except StartupError as exc:
        raise SystemExit(f"Startup refused: {exc}") from None
    return build_app(settings, container, engine)
