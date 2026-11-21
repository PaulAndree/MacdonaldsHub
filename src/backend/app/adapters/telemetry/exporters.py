"""Telemetry destinations: console/local, or Azure Monitor / Application Insights."""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.observability import configure_logging


class ConsoleExporter:
    def configure(self, service_name: str) -> None:
        configure_logging()
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)


class AzureMonitorExporter:
    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

    def configure(self, service_name: str) -> None:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_logging()
        configure_azure_monitor(
            connection_string=self._connection_string,
            resource=Resource.create({"service.name": service_name}),
            logger_name="app",
        )
