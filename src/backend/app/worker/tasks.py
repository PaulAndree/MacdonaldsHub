"""What the single worker does on each tick, as the owner of the work.

Each step is isolated: one that fails is logged and the others still run, so a problem sending mail
cannot stop imports, and the other way round.
"""

import logging
from collections.abc import Callable

from sqlalchemy import Engine

from app.adapters.db.cleanup import SqlCleanupRepository
from app.adapters.db.email_sending import SqlSendingRepository
from app.adapters.db.original_copy import SqlOriginalCopyRepository
from app.adapters.db.preparation import SqlPreparationRepository
from app.composition import Container
from app.domain.mail_rules import unavailable_reason
from app.services.cleanup import CleanupService
from app.services.email_sending import EmailConsumer
from app.services.original_copy import OriginalCopyService
from app.services.ports import MailTransport, OutgoingEmail
from app.services.preparation import PreparationService
from app.settings import Settings

LOG = logging.getLogger("app.worker")


class LazyTransport:
    """The transport is built when something is first sent, so an environment without a mail
    server can run (and report that sending is unavailable) without one."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._transport: MailTransport | None = None

    def send(self, email: OutgoingEmail) -> None:
        if self._transport is None:
            self._transport = self._container.mail()
        self._transport.send(email)


def build_email_consumer(settings: Settings, container: Container, engine: Engine) -> EmailConsumer:
    return EmailConsumer(
        SqlSendingRepository(engine),
        LazyTransport(container),
        sender=settings.smtp_from or "",
        authorized_recipient=settings.test_recipient_email,
        unavailable=lambda: unavailable_reason(
            settings.app_env, settings.smtp_host, settings.smtp_from, settings.test_recipient_email
        ),
    )


def build_work(settings: Settings, container: Container, engine: Engine) -> Callable[[], None]:
    steps: list[tuple[str, Callable[[], object]]] = []
    if settings.imports_enabled:
        storage = container.storage()
        prepare = PreparationService(SqlPreparationRepository(engine), storage)
        copy = OriginalCopyService(SqlOriginalCopyRepository(engine), storage)
        clean = CleanupService(SqlCleanupRepository(engine), storage)
        steps += [
            ("prepare", prepare.process_pending),
            ("copy original", copy.process_pending),
            ("clean up", clean.process_pending),
        ]
    # Sending does not depend on imports: it has its own pause and availability checks.
    steps.append(("send email", build_email_consumer(settings, container, engine).tick))

    def work() -> None:
        for name, step in steps:
            try:
                step()
            except Exception:
                LOG.exception("worker step failed: %s", name)

    return work
