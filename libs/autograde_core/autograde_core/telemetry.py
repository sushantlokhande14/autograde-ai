"""Telemetry bootstrap: structured logging now, OTLP tracing when configured.

Phase 0 keeps this deliberately small: JSON logs via structlog, and — if
OTEL_EXPORTER_OTLP_ENDPOINT is set — a tracer provider that ships spans to the
collector. Instrumentation of individual LLM calls and graders lands in later
phases; this is the wiring they hang off.
"""

from __future__ import annotations

import logging

import structlog

from autograde_core.config import get_settings


def configure_telemetry(service_name: str) -> None:
    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
    )

    if settings.otel_endpoint:
        _configure_tracing(service_name, settings.otel_endpoint)


def _configure_tracing(service_name: str, endpoint: str) -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        structlog.get_logger().warning("otel_sdk_missing", service=service_name)
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
