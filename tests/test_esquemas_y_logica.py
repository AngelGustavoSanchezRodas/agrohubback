import unittest
from starlette.testclient import TestClient
from schemas.telemetria import PayloadESP32, TelemetriaESP32, TelemetriaLecturaRespuesta
from schemas.dispositivos import DispositivoCrear, DispositivoActualizar, DispositivoRespuesta
from schemas.alertas import AlertaAgronomicaCrear, AlertaAgronomicaRespuesta
from api.rutas_sensores import calcular_indice_calor
from core.data_service import formatear_datos_para_ia
from core.security import verificar_api_key
from core.config import settings
from main import app

class TestEsquemasYLogica(unittest.TestCase):
    """Conjunto de pruebas unitarias para el motor de datos y servicios de AgroHub."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_payload_esp32_valores_por_defecto(self) -> None:
        """Verifica que PayloadESP32 acepte datos basicos y asigne valores por defecto de la base de datos."""
        datos = {
            "id_dispositivo": "invernadero_01",
            "temperatura": 24.5,
            "humedad_ambiente": 60.0,
            "humedad_suelo": 45.0,
        }
        payload = PayloadESP32(**datos)
        self.assertEqual(payload.id_dispositivo, "invernadero_01")
        self.assertEqual(payload.temperatura, 24.5)
        self.assertEqual(payload.humedad_ambiente, 60.0)
        self.assertEqual(payload.humedad_suelo, 45.0)
        self.assertEqual(payload.luz_uv, 0.0)
        self.assertIsNone(payload.indice_calor)
        self.assertIsNone(payload.voltaje_bateria)

    def test_payload_esp32_campos_completos(self) -> None:
        """Verifica que PayloadESP32 admita todos los campos correspondientes a telemetria_historica."""
        datos = {
            "id_dispositivo": "nodo_sensor_02",
            "temperatura": 28.0,
            "humedad_ambiente": 75.0,
            "humedad_suelo": 52.3,
            "luz_uv": 4.5,
            "indice_calor": 30.1,
            "voltaje_bateria": 3.85,
        }
        payload = PayloadESP32(**datos)
        self.assertEqual(payload.luz_uv, 4.5)
        self.assertEqual(payload.indice_calor, 30.1)
        self.assertEqual(payload.voltaje_bateria, 3.85)

    def test_calculo_indice_calor(self) -> None:
        """Verifica el calculo del indice de calor con algoritmos meteorologicos estandar."""
        # Temperaturas bajas se mantienen constantes
        self.assertEqual(calcular_indice_calor(18.0, 50.0), 18.0)
        # Temperatura y humedad alta incrementan la sensacion termica
        indice_calor = calcular_indice_calor(30.0, 70.0)
        self.assertGreater(indice_calor, 30.0)

    def test_formateo_datos_para_ia(self) -> None:
        """Verifica que el servicio de datos calcule promedios y genere el resumen temporal para Gemini."""
        datos_prueba = [
            {"temperatura": 24.0, "humedad_ambiente": 60.0, "humedad_suelo": 40.0, "luz_uv": 2.0},
            {"temperatura": 26.0, "humedad_ambiente": 70.0, "humedad_suelo": 50.0, "luz_uv": 4.0},
        ]
        resumen = formatear_datos_para_ia(datos_prueba)
        self.assertIn("Temperatura Ambiente: Promedio 25.0 C", resumen)
        self.assertIn("Maximo: 26.0 C", resumen)
        self.assertIn("Humedad Relativa del Aire: Promedio 65.0%", resumen)
        self.assertIn("Humedad del Sustrato / Suelo: Promedio 45.0%", resumen)

    def test_esquema_dispositivos(self) -> None:
        """Verifica la validacion del esquema de dispositivos segun la tabla de Supabase."""
        dispositivo = DispositivoCrear(
            id_dispositivo="invernadero_01",
            nombre="Estacion Central",
            ubicacion="Modulo A",
            estado_conexion="ACTIVO",
        )
        self.assertEqual(dispositivo.id_dispositivo, "invernadero_01")
        self.assertEqual(dispositivo.estado_conexion, "ACTIVO")

        actualizacion = DispositivoActualizar(estado_conexion="INACTIVO")
        self.assertEqual(actualizacion.estado_conexion, "INACTIVO")
        self.assertIsNone(actualizacion.nombre)

    def test_esquema_alertas_agronomicas(self) -> None:
        """Verifica la definicion del esquema de alertas agronomicas."""
        alerta = AlertaAgronomicaCrear(
            id_dispositivo="invernadero_01",
            tipo_riesgo="ESTRES_HIDRICO",
            severidad="ALTA",
            mensaje_diagnostico="Humedad de suelo critica inferior al 20 por ciento.",
            estado="ACTIVA",
        )
        self.assertEqual(alerta.tipo_riesgo, "ESTRES_HIDRICO")
        self.assertEqual(alerta.severidad, "ALTA")
        self.assertEqual(alerta.estado, "ACTIVA")

    def test_middleware_comunicacion_frontend_api_key(self) -> None:
        """Verifica que el middleware proteja la comunicacion con el frontend exigiendo X-API-Key."""
        # 1. Rutas publicas funcionan sin cabecera
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)

        # 2. Rutas del frontend sin cabecera son denegadas con 403
        res_sin_key = self.client.get("/api/historial")
        self.assertEqual(res_sin_key.status_code, 403)

        # 3. Rutas del frontend con X-API-Key autorizada se ejecutan con exito
        headers = {settings.API_KEY_NOMBRE: settings.API_KEY_SECRETA}
        res_con_key = self.client.get("/api/historial", headers=headers)
        self.assertEqual(res_con_key.status_code, 200)

    def test_rutas_registradas_fastapi(self) -> None:
        """Verifica que las rutas activas de datos e IA esten registradas y las rutas de autenticacion y control hayan sido eliminadas."""
        rutas = list(app.openapi()["paths"].keys())
        self.assertIn("/api/telemetria/ingesta", rutas)
        self.assertIn("/api/telemetria/historial/{id_dispositivo}", rutas)
        self.assertIn("/api/telemetria/historial", rutas)
        self.assertIn("/api/ia/diagnostico/{id_dispositivo}", rutas)
        self.assertIn("/api/ia/barrido", rutas)
        self.assertIn("/api/ia/programador/estado", rutas)
        self.assertIn("/api/dispositivos", rutas)
        self.assertIn("/api/alertas", rutas)
        self.assertIn("/api/historial", rutas)
        self.assertIn("/", rutas)

        # Confirmacion de que las rutas de seguridad complejas (JWT) y control ya no existen
        self.assertNotIn("/api/auth/login", rutas)
        self.assertNotIn("/api/control/bomba", rutas)
        self.assertNotIn("/api/control/actuador", rutas)
        self.assertNotIn("/api/control/historial", rutas)

    def test_diagnostico_agronomico_esquema(self) -> None:
        """Verifica la validacion del esquema DiagnosticoAgronomico usando Pydantic."""
        from core.ia_service import DiagnosticoAgronomico
        diagnostico = DiagnosticoAgronomico(
            estado_general="OPTIMO",
            riesgo_detectado="NINGUNO",
            recomendacion_tecnica="Mantener el riego programado.",
        )
        self.assertEqual(diagnostico.estado_general, "OPTIMO")
        self.assertEqual(diagnostico.riesgo_detectado, "NINGUNO")
        self.assertEqual(diagnostico.recomendacion_tecnica, "Mantener el riego programado.")

    def test_analisis_ia_estructura_respuesta(self) -> None:
        """Verifica que el servicio de IA retorne un diccionario con el contrato estructurado esperado."""
        from core.ia_service import analizar_condiciones_agricolas
        resumen = "Temperatura Ambiente: Promedio 24.5 C. Humedad: 60%."
        resultado = analizar_condiciones_agricolas(resumen, cultivo="Tomate")
        self.assertIsInstance(resultado, dict)
        self.assertIn("estado_general", resultado)
        self.assertIn("riesgo_detectado", resultado)
        self.assertIn("recomendacion_tecnica", resultado)

if __name__ == "__main__":
    unittest.main()
