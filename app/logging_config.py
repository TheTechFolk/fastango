# app/logging_config.py
"""
Fastango — Logging setup.

Called from lifespan, not at import. `logging.basicConfig` as a side effect of
importing app.main hands root-logger INFO to every consumer that imports the
app — Alembic, pytest, any worker — and fights uvicorn's own configuration.

Every line carries the request id, so a 500 in the log can be matched to the
X-Request-ID the client was handed.
"""

import logging

from app.config import settings
from app.core.context import get_request_id

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s"

_configured = False


class RequestIdFilter(logging.Filter):
    """Injects the current request id into every record.

    A filter rather than an adapter: it has to apply to records emitted by
    third-party loggers too, which know nothing about this app.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    """Install the handler on the root logger. Idempotent."""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.APP_DEBUG else logging.INFO)

    _configured = True
