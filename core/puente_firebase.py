import logging
import math
from typing import Any

import firebase_admin
from pydantic import ValidationError

from api.rutas_sensores import calcular_indice_calor, evaluar_alertas_automaticas
from core.config import settings
from db.firebase_client import firebase_db
from db.supabase_client import asegurar_dispositivo_registrado, supabase
from schemas.telemetria import PayloadESP32

logger = logging.getLogger(__name__)

_ultima_marca_por_dispositivo: dict[str, str] = {}
_ultimo_estado_bomba: dict[str, bool] = {}
_listener_firebase: Any = None


def numero_finito(valor: Any) -> float | None:
    """Convierte un valor del JSON de Firebase y descarta NaN o infinito."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero):
        return None
    return numero


def lectura_desde_estado(id_dispositivo: str, estado: dict[str, Any]) -> PayloadESP32 | None:
    """
    Adapta el estado_actual que escribe el ESP32 al contrato de la API.
    Omite la lectura cuando el sensor publica un valor no numerico.
    """
    temperatura = numero_finito(estado.get("temperatura"))
    humedad_ambiente = numero_finito(estado.get("humedad_ambiente"))
    humedad_suelo = numero_finito(estado.get("humedad_suelo"))
    if temperatura is None or humedad_ambiente is None or humedad_suelo is None:
        return None

    lux = numero_finito(estado.get("intensidad_luz_lux"))
    intensidad_luz = max(0.0, lux) if lux is not None else 0.0

    return PayloadESP32(
        id_dispositivo=id_dispositivo,
        temperatura=min(80.0, max(-10.0, temperatura)),
        humedad_ambiente=min(100.0, max(0.0, humedad_ambiente)),
        humedad_suelo=min(100.0, max(0.0, humedad_suelo)),
        intensidad_luz_lux=intensidad_luz,
        estado_bomba=bool(estado.get("estado_bomba")),
    )


def persistir_payload_telemetria(datos: dict[str, Any]) -> bool:
    """
    Valida e inserta en Supabase (telemetria_historica) el payload recibido desde Firebase,
    evitando duplicados y evaluando alertas automaticas y actuadores.
    """
    id_disp = str(datos.get("id_dispositivo") or "").strip()
    if not id_disp or id_disp in settings.DISPOSITIVOS_IGNORADOS:
        return False

    try:
        # Intentar validacion estricta de Pydantic directamente
        payload = PayloadESP32(**datos)
    except ValidationError:
        # Si contiene campos anidados o requiere adaptacion de tipos
        payload = lectura_desde_estado(id_disp, datos)

    if payload is None:
        return False

    marca = str(datos.get("timestamp") or "")
    if not marca:
        marca = f"{payload.temperatura:.1f}_{payload.humedad_ambiente:.1f}_{payload.humedad_suelo:.1f}_{payload.estado_bomba}"

    if _ultima_marca_por_dispositivo.get(id_disp) == marca:
        return False

    try:
        indice = calcular_indice_calor(payload.temperatura, payload.humedad_ambiente)
        asegurar_dispositivo_registrado(payload.id_dispositivo)

        datos_insercion = {
            "id_dispositivo": payload.id_dispositivo,
            "temperatura": payload.temperatura,
            "humedad_ambiente": payload.humedad_ambiente,
            "humedad_suelo": payload.humedad_suelo,
            "intensidad_luz_lux": payload.intensidad_luz_lux,
            "estado_bomba": payload.estado_bomba,
            "indice_calor": indice,
        }

        supabase.table("telemetria_historica").insert(datos_insercion).execute()
        evaluar_alertas_automaticas(payload, indice)

        # Registrar cambios de estado en el actuador de la bomba
        estado_previo_bomba = _ultimo_estado_bomba.get(id_disp)
        if estado_previo_bomba is not None and estado_previo_bomba != payload.estado_bomba:
            try:
                supabase.table("registro_actuadores").insert({
                    "id_dispositivo": payload.id_dispositivo,
                    "actuador": "BOMBA",
                    "accion": "ENCENDIDO" if payload.estado_bomba else "APAGADO",
                    "origen": "ESP32_AUTOMATICO",
                }).execute()
                logger.info(
                    "Cambio de estado de actuador registrado para %s: BOMBA -> %s",
                    payload.id_dispositivo,
                    "ENCENDIDO" if payload.estado_bomba else "APAGADO",
                )
            except Exception as act_err:
                logger.warning("No se pudo registrar actuador en Supabase: %s", str(act_err))
        _ultimo_estado_bomba[id_disp] = payload.estado_bomba
        _ultima_marca_por_dispositivo[id_disp] = marca

        logger.info(
            "Historial guardado exitosamente para %s (T=%.1f C, H=%.1f%%, S=%.1f%%, IC=%.1f C)",
            payload.id_dispositivo,
            payload.temperatura,
            payload.humedad_ambiente,
            payload.humedad_suelo,
            indice,
        )
        return True
    except Exception as e:
        logger.error("Error persistiendo datos en Supabase para %s: %s", id_disp, str(e), exc_info=True)
        return False


def copiar_estados_a_historial() -> int:
    """
    Lee el arbol en vivo de Firebase y guarda en Supabase solo las lecturas nuevas.
    Reutiliza persistir_payload_telemetria para evitar duplicidad logica.
    """
    ruta_nodo = settings.FIREBASE_NODO_TELEMETRIA or "invernadero"
    arbol = firebase_db.reference(ruta_nodo).get()
    if not isinstance(arbol, dict):
        return 0

    guardados = 0
    for id_dispositivo, nodo in arbol.items():
        if not isinstance(nodo, dict):
            continue
        id_str = str(id_dispositivo)
        if id_str in settings.DISPOSITIVOS_IGNORADOS:
            continue
        estado = nodo.get("estado_actual", nodo)
        if isinstance(estado, dict) and ("temperatura" in estado or "humedad_suelo" in estado):
            datos_nodo = dict(estado)
            datos_nodo.setdefault("id_dispositivo", id_str)
            if persistir_payload_telemetria(datos_nodo):
                guardados += 1

    return guardados


def procesar_nueva_telemetria(event: Any) -> None:
    """
    Callback ejecutado por Firebase Realtime Database en un hilo dedicado al detectar
    eventos 'put' o 'patch' en la referencia suscrita.
    """
    if event is None or getattr(event, "data", None) is None:
        return

    data = event.data
    path = getattr(event, "path", "") or ""

    try:
        # Caso 1: Diccionario que ya incluye id_dispositivo y campos de telemetria
        if isinstance(data, dict) and "id_dispositivo" in data and "temperatura" in data:
            persistir_payload_telemetria(data)
            return

        # Caso 2: El path indica el dispositivo (ej: /invernadero_01 o /invernadero_01/estado_actual)
        path_segments = [p for p in path.strip("/").split("/") if p]
        if path_segments and isinstance(data, dict):
            id_disp = path_segments[0]
            estado = data.get("estado_actual", data) if isinstance(data, dict) else {}
            if isinstance(estado, dict) and ("temperatura" in estado or "humedad_suelo" in estado):
                datos_con_id = dict(estado)
                datos_con_id.setdefault("id_dispositivo", id_disp)
                persistir_payload_telemetria(datos_con_id)
                return

        # Caso 3: Diccionario raiz que contiene multiples dispositivos (evento inicial en '/')
        if isinstance(data, dict):
            for clave, subnodo in data.items():
                if isinstance(subnodo, dict):
                    estado = subnodo.get("estado_actual", subnodo)
                    if isinstance(estado, dict) and ("temperatura" in estado or "humedad_suelo" in estado):
                        datos_disp = dict(estado)
                        datos_disp.setdefault("id_dispositivo", str(clave))
                        persistir_payload_telemetria(datos_disp)

    except ValidationError as e:
        logger.warning("Error de validacion Pydantic en datos de Firebase: %s", str(e))
    except Exception as e:
        logger.error("Error inesperado en procesar_nueva_telemetria: %s", str(e), exc_info=True)


def procesar_dato_entrante(evento: Any) -> None:
    """
    Procesa un evento entrante e inserta la telemetria en la tabla telemetria_historica de Supabase,
    incluyendo la intensidad de luz en lux (intensidad_luz_lux).
    """
    if evento is None:
        return

    datos = getattr(evento, "data", None) if not isinstance(evento, dict) else evento
    if isinstance(datos, dict) and "temperatura" in datos:
        try:
            id_disp = str(datos.get("id_dispositivo") or "invernadero_prueba_01").strip()
            asegurar_dispositivo_registrado(id_disp)
            supabase.table("telemetria_historica").insert({
                "id_dispositivo": id_disp,
                "temperatura": datos.get("temperatura"),
                "humedad_ambiente": datos.get("humedad_ambiente"),
                "humedad_suelo": datos.get("humedad_suelo"),
                "intensidad_luz_lux": datos.get("intensidad_luz_lux", 0),
            }).execute()
            logger.info("Telemetria guardada exitosamente en Supabase para %s", id_disp)
        except Exception as e:
            logger.error("Error al guardar en Supabase: %s", str(e), exc_info=True)


# Alias para maxima compatibilidad
procesar_evento_telemetria = procesar_nueva_telemetria


def iniciar_listener_firebase() -> Any:
    """
    Inicia la conexion y escucha en tiempo real de Firebase Realtime Database mediante listen().
    Crea un hilo en segundo plano gestionado por el SDK de Firebase sin bloquear FastAPI.
    """
    global _listener_firebase
    if not firebase_admin._apps:
        logger.warning("No se puede iniciar el listener de Firebase: la aplicacion no ha sido inicializada.")
        return None

    try:
        ruta_nodo = settings.FIREBASE_NODO_TELEMETRIA or "invernadero"
        ref = firebase_db.reference(ruta_nodo)
        logger.info("Iniciando conexion con Firebase Realtime Database en '%s'...", ruta_nodo)
        _listener_firebase = ref.listen(procesar_nueva_telemetria)
        logger.info("Escuchando telemetria en tiempo real...")
        return _listener_firebase
    except Exception as e:
        logger.error("Error al iniciar el listener de Firebase: %s", str(e), exc_info=True)
        return None


def cerrar_listener_firebase() -> None:
    """
    Cierra de forma limpia el listener en segundo plano de Firebase Realtime Database.
    """
    global _listener_firebase
    if _listener_firebase is not None:
        try:
            logger.info("Cerrando listener de Firebase...")
            _listener_firebase.close()
            logger.info("Listener de Firebase cerrado correctamente.")
        except Exception as e:
            logger.error("Error al cerrar el listener de Firebase: %s", str(e))
        finally:
            _listener_firebase = None
