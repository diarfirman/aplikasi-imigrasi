"""
Konfigurasi logging terpusat dengan JSON formatter.

Setiap log record diterbitkan sebagai satu baris JSON ke stdout.
Setiap record secara otomatis menyertakan trace_id dan span_id OTel aktif,
yang di-inject langsung di formatter (tidak butuh LoggingInstrumentor).

Penggunaan:
    from logging_config import setup_logging
    setup_logging(level="INFO")   # panggil sekali, sebelum create_app()

    import logging
    logger = logging.getLogger(__name__)
    logger.info("pesan", extra={"key": "value"})
"""
import json
import logging
from datetime import datetime, timezone


# Field standar pada setiap LogRecord Python — dikecualikan dari pass-through extra
# agar JSON tidak penuh dengan field internal Python yang tidak relevan.
_STANDARD_LOG_RECORD_FIELDS = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "msg", "name",
    "pathname", "process", "processName", "relativeCreated", "stack_info",
    "taskName", "thread", "threadName",
})


class _OTelJsonFormatter(logging.Formatter):
    """
    Format log records ke JSON satu baris, kompatibel dengan Elasticsearch ECS.

    Field yang selalu ada:
        @timestamp  -> ISO-8601 UTC
        level       -> INFO / WARNING / ERROR / dll
        logger      -> nama logger (e.g. "services.search_service")
        message     -> pesan log yang sudah diformat
        trace_id    -> OTel W3C trace_id (32-hex), "" jika tidak ada span aktif
        span_id     -> OTel W3C span_id (16-hex), "" jika tidak ada span aktif

    Field tambahan dari extra={...} di-merge ke root JSON (bukan nested).
    Field "exception" muncul hanya pada log error dengan exc_info=True.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Import lazy di dalam format() untuk menghindari circular import:
        # logging_config bisa diinisialisasi sebelum telemetry.py selesai setup.
        from opentelemetry import trace as otel_trace

        span = otel_trace.get_current_span()
        ctx = span.get_span_context()
        is_valid = ctx is not None and ctx.is_valid

        doc = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": format(ctx.trace_id, "032x") if is_valid else "",
            "span_id": format(ctx.span_id, "016x") if is_valid else "",
        }

        # Merge extra={} fields ke root JSON
        for key, val in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS and not key.startswith("_"):
                doc[key] = val

        if record.exc_info:
            doc["exception"] = self.formatException(record.exc_info)

        return json.dumps(doc, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """
    Inisialisasi logging. Panggil sekali saat startup, sebelum create_app().

    Args:
        level: Log level string, e.g. "INFO", "DEBUG", "WARNING".
    """
    handler = logging.StreamHandler()
    handler.setFormatter(_OTelJsonFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)

    # Kurangi noise dari internal OTel SDK dan Werkzeug
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
