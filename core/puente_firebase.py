import asyncio
import logging
import math
from typing import Any

from api.rutas_sensores import calcular_indice_calor, evaluar_alertas_automaticas
from core.config import settings
from db.firebase_client import firebase_db
from db.supabase_client import asegurar_dispositivo_registrado, supabase
from schemas.telemetria import PayloadESP32

logger = logging.getLogger(__name__)

_ultima_marca_por_dispositivo: dict[str, str] = {}


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
    Adapta el estado_actual que escribe el Heltec al contrato de la API.
    Omite la lectura cuando el DHT22 publica un valor no numerico.
    """
    temperatura = numero_finito(estado.get("temperatura"))
    humedad_ambiente = numero_finito(estado.get("humedad_ambiente"))
    humedad_suelo = numero_finito(estado.get("humedad_suelo"))
    if temperatura is None or humedad_ambiente is None or humedad_suelo is None:
        return None

    luz = numero_finito(estado.get("intensidad_luz_lux"))
    if luz is None:
        luz = 0.0

    return PayloadESP32(
        id_dispositivo=id_dispositivo,
        temperatura=min(80.0, max(-10.0, temperatura)),
        humedad_ambiente=min(100.0, max(0.0, humedad_ambiente)),
        humedad_suelo=min(100.0, max(0.0, humedad_suelo)),
        intensidad_luz_lux=min(100000.0, max(0.0, luz)),
        estado_bomba=bool(estado.get("estado_bomba")),
    )


def copiar_estados_a_historial() -> int:
    """
    Lee el arbol en vivo de Firebase y guarda en Supabase solo las lecturas nuevas.
    El Heltec ya pisa estado_actual; esta copia es la que alimenta graficas y alertas.
    """
    arbol = firebase_db.reference("invernadero").get()
    if not isinstance(arbol, dict):
        return 0

    guardados = 0
    for id_dispositivo, nodo in arbol.items():
        if not isinstance(nodo, dict):
            continue
        id_str = str(id_dispositivo)
        if id_str in settings.DISPOSITIVOS_IGNORADOS:
            continue
        estado = nodo.get("estado_actual")
        if not isinstance(estado, dict):
            continue

        marca = str(estado.get("timestamp") or "")
        if marca and _ultima_marca_por_dispositivo.get(id_str) == marca:
            continue

        payload = lectura_desde_estado(id_str, estado)
        if payload is None:
            logger.warning("Lectura invalida omitida para %s", id_str)
            if marca:
                _ultima_marca_por_dispositivo[id_str] = marca
            continue

        indice_calor = calcular_indice_calor(payload.temperatura, payload.humedad_ambiente)
        asegurar_dispositivo_registrado(payload.id_dispositivo)
        supabase.table("telemetria_historica").insert({
            "id_dispositivo": payload.id_dispositivo,
            "temperatura": payload.temperatura,
            "humedad_ambiente": payload.humedad_ambiente,
            "humedad_suelo": payload.humedad_suelo,
            "luz_uv": payload.luz_uv,
            "intensidad_luz_lux": payload.intensidad_luz_lux,
            "estado_bomba": payload.estado_bomba,
            "indice_calor": indice_calor,
            "voltaje_bateria": payload.voltaje_bateria,
        }).execute()
        evaluar_alertas_automaticas(payload, indice_calor)
        if marca:
            _ultima_marca_por_dispositivo[id_str] = marca
        guardados += 1
        logger.info(
            "Historial actualizado para %s: suelo %.1f %%, bomba %s",
            payload.id_dispositivo,
            payload.humedad_suelo,
            "encendida" if payload.estado_bomba else "apagada",
        )

    return guardados


async def ciclo_puente_firebase() -> None:
    """Copia periodica del estado vivo hacia el historial relacional."""
    intervalo = max(10, settings.PUENTE_FIREBASE_INTERVALO_SEGUNDOS)
    logger.info("Puente Firebase a Supabase iniciado. Intervalo: %d segundos", intervalo)
    while True:
        try:
            guardados = await asyncio.to_thread(copiar_estados_a_historial)
            if guardados:
                logger.info("Puente Firebase guardo %d lectura(s)", guardados)
        except asyncio.CancelledError:
            logger.info("Puente Firebase detenido")
            break
        except Exception as error:
            logger.error("Error en el puente Firebase: %s", str(error))
        await asyncio.sleep(intervalo)
