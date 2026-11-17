"""hola: servicio HTTP de ejemplo en :8080 con trazas, métricas y logs JSON (OpenTelemetry).

Rutas: / → "hola", /healthz y /readyz → "ok", el resto → 404. La SDK lee OTEL_SERVICE_NAME y
OTEL_EXPORTER_OTLP_ENDPOINT del entorno.
"""
import json
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Proxies de la API: se enlazan a los proveedores que fija configurar_telemetria().
log = logging.getLogger("hola")
tracer = trace.get_tracer("hola")
meter = metrics.get_meter("hola")
peticiones = meter.create_counter("hola.peticiones", description="Peticiones atendidas")
duracion = meter.create_histogram("hola.duracion", unit="s", description="Duración de cada petición")

RESPUESTAS = {"/": b"hola\n", "/healthz": b"ok\n", "/readyz": b"ok\n"}


class FormatoJSON(logging.Formatter):
    """Una línea JSON por registro, con trace_id y span_id si hay un span activo."""

    def format(self, record):
        datos = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "nivel": record.levelname,
            "msg": record.getMessage(),
        }
        for campo in ("ruta", "codigo"):
            if hasattr(record, campo):
                datos[campo] = getattr(record, campo)
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            datos["trace_id"] = format(ctx.trace_id, "032x")
            datos["span_id"] = format(ctx.span_id, "016x")
        return json.dumps(datos, ensure_ascii=False)


class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        inicio = time.perf_counter()
        ruta = self.path.split("?", 1)[0]
        if ruta == "/":   # solo / crea span y log: las sondas de salud no llenan Tempo ni Loki
            with tracer.start_as_current_span("GET /", kind=trace.SpanKind.SERVER):
                codigo = self.responder(ruta)
                log.info("petición", extra={"ruta": ruta, "codigo": codigo})
        else:
            codigo = self.responder(ruta)
        # Las rutas desconocidas van juntas: si no, cada URL inventada sería una serie nueva.
        atributos = {"ruta": ruta if ruta in RESPUESTAS else "otra", "codigo": codigo}
        peticiones.add(1, atributos)
        duracion.record(time.perf_counter() - inicio, atributos)

    def responder(self, ruta):
        cuerpo = RESPUESTAS.get(ruta)
        codigo = 200 if cuerpo else 404
        cuerpo = cuerpo or b"no existe\n"
        self.send_response(codigo)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)
        return codigo

    def log_message(self, *args):   # sin el log de acceso por defecto: ya hay uno en JSON
        pass


def crear_servidor(puerto):
    return ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)


def configurar_telemetria():
    trazas = TracerProvider()
    trazas.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(trazas)
    metrics.set_meter_provider(MeterProvider(metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())]))


def main():
    configurar_telemetria()
    salida = logging.StreamHandler(sys.stdout)
    salida.setFormatter(FormatoJSON())
    logging.basicConfig(level=logging.INFO, handlers=[salida])
    servidor = crear_servidor(8080)
    # SIGTERM (al borrar o actualizar el pod): shutdown() desde otro hilo, porque espera a que
    # serve_forever() termine y este hilo es el que lo está ejecutando.
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=servidor.shutdown).start())
    servidor.serve_forever()
    servidor.server_close()
    trace.get_tracer_provider().shutdown()     # vacía las trazas y métricas pendientes
    metrics.get_meter_provider().shutdown()


if __name__ == "__main__":
    main()
