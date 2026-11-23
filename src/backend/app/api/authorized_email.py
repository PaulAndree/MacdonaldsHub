"""The recipient and template authorized right now, for every operation that creates an email."""

from fastapi import Request

from app.domain import email_template
from app.services.confirmation import AuthorizedEmail


def authorized_email(request: Request) -> AuthorizedEmail | None:
    """The recipient and template authorized now: only the configured test recipient (P-01)."""
    recipient = request.app.state.settings.test_recipient_email
    if not recipient:
        return None
    return AuthorizedEmail(
        recipient=recipient,
        template_version=email_template.TEMPLATE_VERSION,
        subject=email_template.SUBJECT,
        body=email_template.BODY,
    )
