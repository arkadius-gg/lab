"""Pruebas de hola: logs JSON con trace_id y rutas HTTP. Ejecutar: python -m unittest -v"""
import json
import logging
import threading
import unittest
import urllib.error
import urllib.request

from opentelemetry.sdk.trace import TracerProvider

from app import FormatoJSON, crear_servidor


def registro(msg):
    return logging.makeLogRecord({"msg": msg, "levelname": "INFO"})


class PruebasLog(unittest.TestCase):
    def test_log_dentro_de_un_span_lleva_trace_id(self):
        with TracerProvider().get_tracer("t").start_as_current_span("s") as span:
            datos = json.loads(FormatoJSON().format(registro("hola")))
        ctx = span.get_span_context()
        self.assertEqual(datos["trace_id"], format(ctx.trace_id, "032x"))
        self.assertEqual(datos["span_id"], format(ctx.span_id, "016x"))
        self.assertEqual(datos["msg"], "hola")

    def test_log_sin_span_no_lleva_trace_id(self):
        datos = json.loads(FormatoJSON().format(registro("hola")))
        self.assertNotIn("trace_id", datos)


class PruebasRutas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = crear_servidor(0)   # puerto 0: el sistema elige uno libre
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pedir(self, ruta):
        try:
            with urllib.request.urlopen(self.url + ruta, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_raiz(self):
        self.assertEqual(self.pedir("/"), (200, b"hola\n"))

    def test_salud(self):
        for ruta in ("/healthz", "/readyz"):
            self.assertEqual(self.pedir(ruta), (200, b"ok\n"), ruta)

    def test_ruta_desconocida(self):
        self.assertEqual(self.pedir("/nada")[0], 404)
