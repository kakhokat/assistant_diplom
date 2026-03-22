from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from core.settings import settings

logger = logging.getLogger(__name__)

_httpx_instrumentor: HTTPXClientInstrumentor | None = None


def setup_tracing(app) -> None:
    if not settings.OTEL_ENABLED:
        return

    # Важно: трассировка не должна валить сервис (fail-open)
    try:
        resource = Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME or settings.PROJECT_NAME,
                "deployment.environment": settings.APP_ENV,
            }
        )

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        # FastAPI
        try:
            FastAPIInstrumentor.instrument_app(app)
        except Exception as e:  # noqa: BLE001
            logger.warning("FastAPI instrumentation disabled: %s", e)

        # HTTPX (✅ FIX: нужен экземпляр, а не вызов метода класса)
        global _httpx_instrumentor
        try:
            _httpx_instrumentor = HTTPXClientInstrumentor()
            _httpx_instrumentor.instrument()
        except Exception as e:  # noqa: BLE001
            logger.warning("HTTPX instrumentation disabled: %s", e)

        app.state.tracer_provider = provider

    except Exception as e:  # noqa: BLE001
        logger.exception("Tracing setup failed (ignored): %s", e)


def shutdown_tracing(app) -> None:
    provider = getattr(app.state, "tracer_provider", None)

    # best-effort: ничего не роняем
    try:
        global _httpx_instrumentor
        if _httpx_instrumentor is not None:
            try:
                _httpx_instrumentor.uninstrument()
            except Exception:  # noqa: BLE001
                pass
            _httpx_instrumentor = None
    finally:
        if provider is not None:
            try:
                provider.shutdown()
            except Exception:  # noqa: BLE001
                pass
