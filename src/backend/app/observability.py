"""Cross-cutting observability: secret redaction, structured access log, correlation (RNF-05)."""

import json
import logging
import re
import sys
import uuid

_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(AccountKey|SharedAccessKey|Password|Pwd)=[^;&\s\"']+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)([?&;]sig)=[^&\s\"']+"), r"\1=[REDACTED]"),
    (
        re.compile(r"(?i)\b(authorization|cookie|set-cookie)\b(\"?\s*[:=]\s*\"?)[^,\"}\n]+"),
        r"\1\2[REDACTED]",
    ),
    (
        re.compile(r"(?i)(x-ms-client-principal[\w-]*)(\"?\s*[:=]\s*\"?)[^,\"}\n]+"),
        r"\1\2[REDACTED]",
    ),
    (re.compile(r"(?i)(\w+(?:\+\w+)?://[^:/\s]+:)[^@\s]+@"), r"\1[REDACTED]@"),
]

_CORRELATION_OK = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def redact(text: str) -> str:
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


class SecretRedactionFilter(logging.Filter):
    """Masks secrets in every record, whatever logger produced it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(SecretRedactionFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def new_correlation_id(incoming: str | None = None) -> str:
    """Reuse a well-formed incoming id, otherwise generate one (never trust arbitrary text)."""
    if incoming and _CORRELATION_OK.match(incoming):
        return incoming
    return uuid.uuid4().hex


def result_for_status(status: int) -> str:
    if status < 400:
        return "success"
    if status in (401, 403):
        return "denied"
    if status < 500:
        return "rejected"
    return "error"


def log_event(logger: logging.Logger, **fields: object) -> None:
    logger.info(json.dumps(fields, default=str, sort_keys=True))
