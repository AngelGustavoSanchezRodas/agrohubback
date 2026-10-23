import unittest
from starlette.testclient import TestClient
from schemas.telemetria import PayloadESP32, TelemetriaESP32, TelemetriaLecturaRespuesta
from schemas.dispositivos import DispositivoCrear, DispositivoActualizar, DispositivoRespuesta
from schemas.alertas import AlertaAgronomicaCrear, AlertaAgronomicaRespuesta
from schemas.actuadores import RegistroActuadorCrear, RegistroActuadorRespuesta
from datetime import datetime
from fastapi import HTTPException
from api.rutas_sensores import calcular_indice_calor, es_horario_diurno, ZONA_INVERNADERO
from core.puente_firebase import lectura_desde_estado, numero_finito
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
        self.assertFalse(payload.estado_bomba)

    def test_payload_esp32_campos_completos(self) -> None:
        """Verifica que PayloadESP32 admita exactamente los campos del hardware del invernadero."""
        datos = {
            "id_dispositivo": "nodo_sensor_02",
            "temperatura": 28.0,
            "humedad_ambiente": 75.0,
            "humedad_suelo": 52.3,
            "estado_bomba": True,
        }
        payload = PayloadESP32(**datos)
        self.assertEqual(payload.id_dispositivo, "nodo_sensor_02")
        self.assertEqual(payload.temperatura, 28.0)
        self.assertEqual(payload.humedad_ambiente, 75.0)
        self.assertEqual(payload.humedad_suelo, 52.3)
        self.assertTrue(payload.estado_bomba)

    def test_lectura_firebase_descarta_nan_del_dht22(self) -> None:
        """Una lectura NaN del DHT22 no debe entrar al historial."""
        self.assertIsNone(numero_finito(float("nan")))
        self.assertIsNone(lectura_desde_estado("invernadero_prueba_01", {
            "temperatura": float("nan"),
            "humedad_ambiente": 70.0,
            "humedad_suelo": 40.0,
        }))

    def test_lectura_firebase_ajusta_suelo_al_rango_valido(self) -> None:
        """El mapeo ADC del microcontrolador puede salir de 0 a 100. El contrato lo recorta."""
        payload = lectura_desde_estado("invernadero_prueba_01", {
            "temperatura": 24.0,
            "humedad_ambiente": 60.0,
            "humedad_suelo": 140.0,
            "estado_bomba": True,
        })
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload.humedad_suelo, 100.0)
        self.assertTrue(payload.estado_bomba)

    def test_horario_diurno_para_alerta_de_luz(self) -> None:
        """La alerta de poca luz del TSL2561 solo corresponde al horario diurno local."""
        self.assertTrue(es_horario_diurno(datetime(2026, 10, 19, 10, 0, tzinfo=ZONA_INVERNADERO)))
        self.assertFalse(es_horario_diurno(datetime(2026, 10, 19, 22, 0, tzinfo=ZONA_INVERNADERO)))

    def test_calculo_indice_calor(self) -> None:
        """Verifica el calculo del indice de calor con algoritmos meteorologicos estandar."""
        # Temperaturas menores a 26.7 C retornan la misma temperatura
        self.assertEqual(calcular_indice_calor(18.0, 50.0), 18.0)
        self.assertEqual(calcular_indice_calor(26.6, 60.0), 26.6)
        # Temperatura mayor o igual a 26.7 C y humedad alta incrementan la sensacion termica
        indice_calor = calcular_indice_calor(30.0, 70.0)
        self.assertGreater(indice_calor, 30.0)
        # Verificacion con paso de parametros nombrados
        indice_kw = calcular_indice_calor(temperatura_c=30.0, humedad=70.0)
        self.assertEqual(indice_calor, indice_kw)

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
            cultivo="Lechuga",
        )
        self.assertEqual(dispositivo.id_dispositivo, "invernadero_01")
        self.assertEqual(dispositivo.estado_conexion, "ACTIVO")
        self.assertEqual(dispositivo.cultivo, "Lechuga")

        actualizacion = DispositivoActualizar(estado_conexion="INACTIVO", cultivo="Tomate")
        self.assertEqual(actualizacion.estado_conexion, "INACTIVO")
        self.assertEqual(actualizacion.cultivo, "Tomate")
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

    def test_esquema_registro_actuadores(self) -> None:
        """Verifica la validacion del esquema para la tabla public.registro_actuadores."""
        actuador = RegistroActuadorCrear(
            id_dispositivo="invernadero_prueba_01",
            actuador="BOMBA",
            accion="ENCENDIDO",
            origen="ESP32_AUTO",
        )
        self.assertEqual(actuador.id_dispositivo, "invernadero_prueba_01")
        self.assertEqual(actuador.actuador, "BOMBA")
        self.assertEqual(actuador.accion, "ENCENDIDO")
        self.assertEqual(actuador.origen, "ESP32_AUTO")

    def test_payload_esp32_codigo_cpp(self) -> None:
        """Verifica que PayloadESP32 admita exactamente el payload generado por el Heltec V3 en C++."""
        datos_cpp = {
            "id_dispositivo": "invernadero_prueba_01",
            "temperatura": 25.5,
            "humedad_ambiente": 60.0,
            "humedad_suelo": 45.0,
            "estado_bomba": False,
        }
        payload = PayloadESP32(**datos_cpp)
        self.assertEqual(payload.temperatura, 25.5)
        self.assertEqual(payload.humedad_ambiente, 60.0)
        self.assertEqual(payload.humedad_suelo, 45.0)
        self.assertFalse(payload.estado_bomba)
        self.assertEqual(payload.intensidad_luz_lux, 0.0)

    def test_middleware_comunicacion_frontend_api_key(self) -> None:
        """Verifica que el middleware proteja la comunicacion exigiendo estrictamente X-API-Key sin bypass."""
        # 1. Rutas publicas funcionan sin cabecera
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)

        # 2. Rutas del frontend sin cabecera son denegadas con 403
        res_sin_key = self.client.get("/api/historial")
        self.assertEqual(res_sin_key.status_code, 403)

        # 3. Intentos de bypass mediante spoofing de cabecera Origin son rechazados con 403
        res_spoof = self.client.get("/api/historial", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(res_spoof.status_code, 403)

        # 4. Claves obsoletas o quemadas son denegadas con 403
        res_clave_quemada = self.client.get(
            "/api/historial", 
            headers={settings.API_KEY_NOMBRE: "clave_estatica_agrohub_123"}
        )
        self.assertEqual(res_clave_quemada.status_code, 403)

        # 5. Rutas con X-API-Key autorizada de configuracion se ejecutan con exito
        headers = {settings.API_KEY_NOMBRE: settings.API_KEY_SECRETA}
        res_con_key = self.client.get("/api/historial", headers=headers)
        self.assertEqual(res_con_key.status_code, 200)

    def test_rutas_registradas_fastapi(self) -> None:
        """Verifica que las rutas activas de consulta, sincronizacion, IA y actuadores esten registradas."""
        rutas = list(app.openapi()["paths"].keys())
        self.assertNotIn("/api/telemetria/ingesta", rutas)
        self.assertNotIn("/api/telemetria", rutas)
        self.assertIn("/api/telemetria/sincronizar", rutas)
        self.assertIn("/api/telemetria/historial/{id_dispositivo}", rutas)
        self.assertIn("/api/telemetria/historial", rutas)
        self.assertIn("/api/ia/diagnostico/{id_dispositivo}", rutas)
        self.assertIn("/api/ia/barrido", rutas)
        self.assertIn("/api/ia/programador/estado", rutas)
        self.assertIn("/api/dispositivos", rutas)
        self.assertIn("/api/alertas", rutas)
        self.assertIn("/api/actuadores", rutas)
        self.assertIn("/api/actuadores/historial/{id_dispositivo}", rutas)
        self.assertIn("/api/historial", rutas)
        self.assertIn("/", rutas)

        # Confirmacion de que no existen rutas de ingesta HTTP ni autenticaciones complejas
        self.assertNotIn("/api/auth/login", rutas)
        self.assertNotIn("/api/control/bomba", rutas)
        self.assertNotIn("/api/control/actuador", rutas)
        self.assertNotIn("/api/control/historial", rutas)

    def test_endpoint_sincronizar_telemetria_validacion(self) -> None:
        """Verifica que el endpoint /api/telemetria/sincronizar valide estrictamente el esquema PayloadESP32."""
        headers = {settings.API_KEY_NOMBRE: settings.API_KEY_SECRETA}
        # Carga invalida con temperatura fuera de rango permitido (-10 a 80 C)
        payload_invalido = {
            "id_dispositivo": "invernadero_01",
            "temperatura": 120.0,
            "humedad_ambiente": 60.0,
            "humedad_suelo": 45.0,
        }
        res = self.client.post("/api/telemetria/sincronizar", json=payload_invalido, headers=headers)
        self.assertEqual(res.status_code, 422)

    def test_diagnostico_agronomico_esquema(self) -> None:
        """Verifica la validacion del esquema DiagnosticoAgronomico usando Pydantic."""
        from core.ia_service import DiagnosticoAgronomico
        diagnostico = DiagnosticoAgronomico(
            estado_general="OPTIMO",
            riesgo_detectado="NINGUNO",
            evaluacion_humedad="Humedad en rango optimo.",
            evaluacion_luz="Iluminacion adecuada para fotosintesis.",
            recomendacion_tecnica="Mantener el riego programado.",
        )
        self.assertEqual(diagnostico.estado_general, "OPTIMO")
        self.assertEqual(diagnostico.riesgo_detectado, "NINGUNO")
        self.assertEqual(diagnostico.evaluacion_humedad, "Humedad en rango optimo.")
        self.assertEqual(diagnostico.evaluacion_luz, "Iluminacion adecuada para fotosintesis.")
        self.assertEqual(diagnostico.recomendacion_tecnica, "Mantener el riego programado.")

        # Verificar asignacion de valores por defecto cuando no se especifican evaluaciones
        diag_defaults = DiagnosticoAgronomico(
            estado_general="ADVERTENCIA",
            riesgo_detectado="ESTRES_HIDRICO",
            recomendacion_tecnica="Aumentar frecuencia de riego.",
        )
        self.assertEqual(diag_defaults.evaluacion_humedad, "Sin evaluacion de humedad especificada")
        self.assertEqual(diag_defaults.evaluacion_luz, "Sin evaluacion de luz especificada")

    def test_analisis_ia_estructura_respuesta(self) -> None:
        """Verifica que el servicio de IA retorne un diccionario con el contrato estructurado esperado."""
        from core.ia_service import analizar_condiciones_agricolas
        resumen = "Temperatura Ambiente: Promedio 24.5 C. Humedad: 60%."
        resultado = analizar_condiciones_agricolas(resumen, cultivo="Tomate")
        self.assertIsInstance(resultado, dict)
        self.assertIn("estado_general", resultado)
        self.assertIn("riesgo_detectado", resultado)
        self.assertIn("recomendacion_tecnica", resultado)

    def test_procesar_nueva_telemetria_data_nula(self) -> None:
        """Verifica que el callback del listener de Firebase descarte eventos con datos nulos."""
        from core.puente_firebase import procesar_nueva_telemetria
        class MockEvent:
            data = None
            path = "/"
        # No debe lanzar ninguna excepcion
        procesar_nueva_telemetria(MockEvent())

    def test_procesar_nueva_telemetria_datos_invalidos(self) -> None:
        """Verifica que el callback del listener capture y maneje errores de validacion sin detener el servidor."""
        from core.puente_firebase import procesar_nueva_telemetria
        class MockEvent:
            data = {
                "id_dispositivo": "invernadero_err_01",
                "temperatura": "valor_no_numerico",
            }
            path = "/"
        # Debe capturar el error y no propagar excepcion no controlada
        procesar_nueva_telemetria(MockEvent())

    def test_esquema_telemetria_historica_y_extendida(self) -> None:
        """Verifica los esquemas de persistencia historica y respuestas detalladas de sensores."""
        telemetria = TelemetriaESP32(
            id_dispositivo="invernadero_01",
            temperatura=25.0,
            humedad_ambiente=65.0,
            humedad_suelo=50.0,
            luz_uv=1.2,
            intensidad_luz_lux=15000.0,
            estado_bomba=True,
            indice_calor=25.5,
            voltaje_bateria=3.7,
        )
        self.assertEqual(telemetria.id_dispositivo, "invernadero_01")
        self.assertEqual(telemetria.intensidad_luz_lux, 15000.0)
        self.assertEqual(telemetria.voltaje_bateria, 3.7)

        lectura = TelemetriaLecturaRespuesta(
            id=101,
            id_dispositivo="invernadero_01",
            temperatura=25.0,
            humedad_ambiente=65.0,
            humedad_suelo=50.0,
            luz_uv=1.2,
            intensidad_luz_lux=15000.0,
            estado_bomba=True,
            indice_calor=25.5,
            voltaje_bateria=3.7,
            creado_en="2026-10-21T10:00:00Z",
        )
        self.assertEqual(lectura.id, 101)
        self.assertEqual(lectura.creado_en, "2026-10-21T10:00:00Z")

    def test_esquemas_respuesta_modelos_relacionales(self) -> None:
        """Verifica que los modelos de respuesta de dispositivos, alertas y actuadores validen correctamente."""
        disp_resp = DispositivoRespuesta(
            id_dispositivo="invernadero_01",
            nombre="Modulo Central",
            ubicacion="Seccion A",
            fecha_instalacion="2026-10-20T08:00:00Z",
            estado_conexion="ACTIVO",
            cultivo="Tomate",
        )
        self.assertEqual(disp_resp.id_dispositivo, "invernadero_01")
        self.assertEqual(disp_resp.cultivo, "Tomate")

        alerta_resp = AlertaAgronomicaRespuesta(
            id=1,
            id_dispositivo="invernadero_01",
            tipo_riesgo="ESTRES_HIDRICO",
            severidad="ALTA",
            mensaje_diagnostico="Riego urgente requerido",
            estado="ACTIVA",
            creado_en="2026-10-21T09:00:00Z",
        )
        self.assertEqual(alerta_resp.id, 1)
        self.assertIsNone(alerta_resp.resuelta_en)

        actuador_resp = RegistroActuadorRespuesta(
            id=5,
            id_dispositivo="invernadero_01",
            actuador="BOMBA",
            accion="ENCENDIDO",
            origen="ESP32_AUTO",
            creado_en="2026-10-21T09:05:00Z",
        )
        self.assertEqual(actuador_resp.id, 5)
        self.assertEqual(actuador_resp.actuador, "BOMBA")

    def test_funcion_verificar_api_key_directa(self) -> None:
        """Verifica el comportamiento de la funcion de seguridad verificar_api_key."""
        # Clave autorizada retorna la misma clave
        clave_valida = settings.API_KEY_SECRETA
        self.assertEqual(verificar_api_key(clave_valida), clave_valida)

        # Clave invalida genera HTTPException con codigo 403
        with self.assertRaises(HTTPException) as ctx:
            verificar_api_key("clave_no_autorizada_invalida")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_obtener_contexto_invernadero_tipo_retorno(self) -> None:
        """Verifica que obtener_contexto_invernadero siempre retorne un diccionario valido."""
        from core.data_service import obtener_contexto_invernadero
        contexto = obtener_contexto_invernadero("dispositivo_inexistente_999")
        self.assertIsInstance(contexto, dict)

    def test_analizar_condiciones_estructura_respuesta(self) -> None:
        """Verifica que analizar_condiciones devuelva el contrato estructurado esperado para la IA."""
        from core.ia_service import analizar_condiciones
        resumen = "Temperatura Ambiente: Promedio 24.5 C. Humedad: 60%."
        resultado = analizar_condiciones(
            id_dispositivo="invernadero_01",
            resumen_telemetria=resumen,
        )
        self.assertIsInstance(resultado, dict)
        self.assertIn("estado_general", resultado)
        self.assertIn("riesgo_detectado", resultado)
        self.assertIn("evaluacion_humedad", resultado)
        self.assertIn("evaluacion_luz", resultado)
        self.assertIn("recomendacion_tecnica", resultado)

    def test_esquema_dispositivo_con_id_invernadero(self) -> None:
        """Verifica que los esquemas de dispositivos admitan la clave foranea id_invernadero."""
        disp = DispositivoCrear(
            id_dispositivo="nodo_01",
            nombre="Nodo Sector Norte",
            id_invernadero=1,
            cultivo="Tomate",
        )
        self.assertEqual(disp.id_invernadero, 1)

        actualizacion = DispositivoActualizar(id_invernadero=2)
        self.assertEqual(actualizacion.id_invernadero, 2)

        resp = DispositivoRespuesta(
            id_dispositivo="nodo_01",
            nombre="Nodo Sector Norte",
            id_invernadero=1,
        )
        self.assertEqual(resp.id_invernadero, 1)

    def test_payload_esp32_con_intensidad_luz_lux(self) -> None:
        """Verifica que PayloadESP32 admita el campo intensidad_luz_lux correctamente."""
        datos = {
            "id_dispositivo": "invernadero_prueba_01",
            "temperatura": 25.0,
            "humedad_ambiente": 62.0,
            "humedad_suelo": 48.0,
            "intensidad_luz_lux": 1450.5,
        }
        payload = PayloadESP32(**datos)
        self.assertEqual(payload.intensidad_luz_lux, 1450.5)

    def test_procesar_dato_entrante_guarda_en_supabase(self) -> None:
        """Verifica que procesar_dato_entrante procese el evento e intente la insercion con luz."""
        from unittest.mock import patch, MagicMock
        from core.puente_firebase import procesar_dato_entrante

        class EventoPrueba:
            data = {
                "id_dispositivo": "invernadero_prueba_01",
                "temperatura": 23.4,
                "humedad_ambiente": 55.0,
                "humedad_suelo": 42.0,
                "intensidad_luz_lux": 1200.0,
            }

        with patch("core.puente_firebase.supabase") as mock_sb:
            mock_table = MagicMock()
            mock_insert = MagicMock()
            mock_execute = MagicMock()
            mock_sb.table.return_value = mock_table
            mock_table.insert.return_value = mock_insert
            mock_insert.execute.return_value = mock_execute

            procesar_dato_entrante(EventoPrueba())

            mock_sb.table.assert_called_with("telemetria_historica")
            mock_table.insert.assert_called_once()
            args_insertados = mock_table.insert.call_args[0][0]
            self.assertEqual(args_insertados["id_dispositivo"], "invernadero_prueba_01")
            self.assertEqual(args_insertados["temperatura"], 23.4)
            self.assertEqual(args_insertados["intensidad_luz_lux"], 1200.0)

if __name__ == "__main__":
    unittest.main()
