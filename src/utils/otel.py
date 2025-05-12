import os
import base64
from src.config.settings import settings

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_otlp_initialized = False


def init_otel():
    global _otlp_initialized
    if _otlp_initialized:
        return
    if not (
        settings.LANGFUSE_PUBLIC_KEY
        and settings.LANGFUSE_SECRET_KEY
        and settings.OTEL_EXPORTER_OTLP_ENDPOINT
    ):
        return

    langfuse_auth = base64.b64encode(
        f"{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}".encode()
    ).decode()
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {langfuse_auth}"

    provider = TracerProvider(
        resource=Resource.create({"service.name": "evo_ai_agent"})
    )
    exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _otlp_initialized = True


def get_tracer(name: str = "evo_ai_agent"):
    return trace.get_tracer(name)
