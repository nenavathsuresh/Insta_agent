"""
shared/observability.py
-----------------------
Centralised OpenTelemetry + structured-logging bootstrap.

Call ``setup_observability()`` once at application startup.  Both the
FoundryChatClient agent and the OpenAIChatClient agent import this module so
telemetry config is identical across both.
"""

from __future__ import annotations

import logging
import logging.config
import os
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Structured / JSON logging
# ---------------------------------------------------------------------------
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "plain": {
            "format": "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "plain",  # switch to "json" for production log aggregators
        },
    },
    "root": {
        "level": os.getenv("LOG_LEVEL", "INFO"),
        "handlers": ["console"],
    },
    "loggers": {
        "agent": {"level": "DEBUG", "propagate": True},
        "httpx": {"level": "WARNING", "propagate": True},
        "opentelemetry": {"level": "WARNING", "propagate": True},
    },
}


def setup_logging(json_output: bool = False) -> None:
    if json_output:
        LOGGING_CONFIG["handlers"]["console"]["formatter"] = "json"  # type: ignore[index]
    try:
        logging.config.dictConfig(LOGGING_CONFIG)
    except Exception:
        # Fallback if python-json-logger is not installed
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            stream=sys.stdout,
        )


# ---------------------------------------------------------------------------
# OpenTelemetry bootstrap
# ---------------------------------------------------------------------------
def setup_opentelemetry(
    service_name: str,
    otlp_endpoint: Optional[str] = None,
    azure_connection_string: Optional[str] = None,
    enable_console_exporter: bool = False,
) -> None:
    """
    Configure OpenTelemetry tracing + metrics.

    Priority:
      1. Azure Monitor (Application Insights) if ``azure_connection_string`` is set
         or env var ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is present.
      2. OTLP exporter if ``otlp_endpoint`` is set or
         env var ``OTEL_EXPORTER_OTLP_ENDPOINT`` is present.
      3. Console exporter for local development when ``enable_console_exporter=True``.
    """
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": service_name})

    # ---- Tracer ----
    tp = TracerProvider(resource=resource)

    # ---- Metric reader list ----
    readers = []

    ai_conn = azure_connection_string or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    otlp_ep = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if ai_conn:
        try:
            from azure.monitor.opentelemetry.exporter import (  # type: ignore
                AzureMonitorMetricExporter,
                AzureMonitorTraceExporter,
            )

            tp.add_span_processor(
                BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=ai_conn))
            )
            readers.append(
                PeriodicExportingMetricReader(
                    AzureMonitorMetricExporter(connection_string=ai_conn)
                )
            )
            logging.getLogger("agent.observability").info(
                "OpenTelemetry → Azure Monitor (Application Insights)"
            )
        except ImportError:
            logging.warning(
                "azure-monitor-opentelemetry-exporter not installed; "
                "skipping Azure Monitor exporter."
            )

    elif otlp_ep:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # type: ignore
                OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore
                OTLPSpanExporter,
            )

            tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_ep)))
            readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otlp_ep)))
            logging.getLogger("agent.observability").info(
                "OpenTelemetry → OTLP endpoint %s", otlp_ep
            )
        except ImportError:
            logging.warning(
                "opentelemetry-exporter-otlp-proto-grpc not installed; skipping OTLP exporter."
            )

    if enable_console_exporter or (not ai_conn and not otlp_ep):
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        tp.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logging.getLogger("agent.observability").info(
            "OpenTelemetry → console (development mode)"
        )

    trace.set_tracer_provider(tp)

    mp = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(mp)


# ---------------------------------------------------------------------------
# Convenience one-shot bootstrap
# ---------------------------------------------------------------------------
def setup_observability(
    service_name: str = "mcp-agent",
    json_logs: bool = False,
    otlp_endpoint: Optional[str] = None,
    azure_connection_string: Optional[str] = None,
    enable_console_exporter: bool = False,
) -> None:
    """Call once at the top of ``main()``."""
    setup_logging(json_output=json_logs)
    setup_opentelemetry(
        service_name=service_name,
        otlp_endpoint=otlp_endpoint,
        azure_connection_string=azure_connection_string,
        enable_console_exporter=enable_console_exporter,
    )
