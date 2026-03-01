"""
Bootstrap OpenTelemetry SDK.

Panggil setup_telemetry(app) sekali di dalam create_app(), setelah Flask app dibuat.

Provider yang diinisialisasi:
  - TracerProvider  -> BatchSpanProcessor -> OTLPSpanExporter (HTTP/proto)
  - MeterProvider   -> PeriodicExportingMetricReader -> OTLPMetricExporter
  - LoggerProvider  -> BatchLogRecordProcessor -> OTLPLogExporter (HTTP/proto)
    + LoggingHandler yang menjembatani Python logging -> OTel logs -> Elasticsearch

Instrumentor yang diaktifkan:
  - FlaskInstrumentor       (span HTTP otomatis untuk setiap route)
  - ElasticsearchInstrumentor (span DB otomatis untuk setiap query ES)

Helper:
  - get_tracer(name) -> trace.Tracer  (noop sebelum setup_telemetry dipanggil)
  - get_meter(name)  -> metrics.Meter (noop sebelum setup_telemetry dipanggil)
"""
import logging

from opentelemetry import trace, metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk.resources import (
    Resource,
    SERVICE_NAME,
    SERVICE_VERSION,
    DEPLOYMENT_ENVIRONMENT,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor

logger = logging.getLogger(__name__)


def setup_telemetry(app) -> None:
    """
    Inisialisasi semua OTel provider dan instrumentor.

    Harus dipanggil setelah Flask app dibuat dan sebelum blueprint didaftarkan.
    FlaskInstrumentor memerlukan objek app yang sudah ada.
    ElasticsearchInstrumentor meng-patch class ES secara global.
    """
    from config import Config

    resource = Resource.create({
        SERVICE_NAME: Config.OTEL_SERVICE_NAME,
        SERVICE_VERSION: Config.OTEL_SERVICE_VERSION,
        DEPLOYMENT_ENVIRONMENT: Config.OTEL_ENVIRONMENT,
    })
    endpoint = Config.OTEL_ENDPOINT
    headers = Config.OTEL_HEADERS

    # ── Traces ────────────────────────────────────────────────────────────────
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=f"{endpoint}/v1/traces",
                headers=headers,
            )
        )
    )
    trace.set_tracer_provider(tracer_provider)

    # ── Metrics ───────────────────────────────────────────────────────────────
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=f"{endpoint}/v1/metrics",
                    headers=headers,
                ),
                export_interval_millis=30_000,  # export setiap 30 detik
            )
        ],
    )
    metrics.set_meter_provider(meter_provider)

    # ── Logs (OTel log pipeline -> Elasticsearch via OTLP) ────────────────────
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(
                endpoint=f"{endpoint}/v1/logs",
                headers=headers,
            )
        )
    )
    set_logger_provider(logger_provider)

    # Jembatani Python logging -> OTel logs pipeline
    # Level INFO: hanya log INFO ke atas yang dikirim ke Elasticsearch
    # (DEBUG terlalu verbose untuk disimpan di ES)
    otel_log_handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=logger_provider,
    )
    logging.getLogger().addHandler(otel_log_handler)

    # ── Auto-Instrumentation ──────────────────────────────────────────────────
    FlaskInstrumentor().instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
    ElasticsearchInstrumentor().instrument(
        tracer_provider=tracer_provider,
    )

    logger.info(
        "OpenTelemetry initialized",
        extra={
            "otel_endpoint": endpoint,
            "service_name": Config.OTEL_SERVICE_NAME,
            "service_version": Config.OTEL_SERVICE_VERSION,
            "environment": Config.OTEL_ENVIRONMENT,
        },
    )


def get_tracer(name: str = "checkpoint-imigrasi") -> trace.Tracer:
    """
    Kembalikan tracer. Aman dipanggil sebelum setup_telemetry()
    (akan mengembalikan noop tracer sampai provider diset).
    """
    return trace.get_tracer(name)


def get_meter(name: str = "checkpoint-imigrasi") -> metrics.Meter:
    """
    Kembalikan meter. Aman dipanggil sebelum setup_telemetry()
    (akan mengembalikan noop meter sampai provider diset).
    """
    return metrics.get_meter(name)
