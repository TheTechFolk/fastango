# app/core/audit.py
import logging

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("fastango.audit")


class AuditLogService:
    """
    Asynchronous audit logging service.

    Records request metadata (method, path, status, duration) for every
    processed HTTP request.  In production this would persist records to an
    AuditLog database table via an injected AsyncSession.
    """

    @staticmethod
    async def log_request(
        request: Request,
        response: Response,
        process_time: float,
        db: AsyncSession | None = None,
    ) -> None:
        """
        Capture and persist request/response metadata.

        Args:
            request: The incoming FastAPI Request object.
            response: The outgoing Response object.
            process_time: Total processing duration in seconds.
            db: Optional database session for persisting audit records.
        """
        log_entry = {
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
        }

        logger.info(
            "[AUDIT] %(method)s %(path)s → %(status_code)s in %(process_time_ms)sms",
            log_entry,
        )

        # ── Persist to DB (stub — wire up your AuditLog ORM model here) ──────
        # if db:
        #     audit = AuditLog(**log_entry)
        #     db.add(audit)
        #     await db.flush()
