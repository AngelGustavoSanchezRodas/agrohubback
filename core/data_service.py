import logging
from typing import Any
from db.supabase_client import supabase

logger = logging.getLogger(__name__)

def obtener_historial_reciente(id_dispositivo: str, limite: int = 24) -> list[dict[str, Any]]:
    """
    Extrae el historial de telemetria mas reciente de un dispositivo especifico desde Supabase.
    """
    try:
        respuesta = (
            supabase.table("telemetria_historica")
            .select("*")
            .eq("id_dispositivo", id_dispositivo)
            .order("creado_en", desc=True)
            .limit(limite)
            .execute()
        )
        return respuesta.data or []
    except Exception as e:
        logger.error("Error al obtener historial reciente para %s: %s", id_dispositivo, str(e))
        return []

def obtener_historial_general(limite: int = 50) -> list[dict[str, Any]]:
    """
    Extrae el historial general mas reciente de telemetria de todos los dispositivos.
    """
    try:
        respuesta = (
            supabase.table("telemetria_historica")
            .select("*")
            .order("creado_en", desc=True)
            .limit(limite)
            .execute()
        )
        return respuesta.data or []
    except Exception as e:
        logger.error("Error al obtener historial general de telemetria: %s", str(e))
        return []

def obtener_contexto_invernadero(id_dispositivo: str) -> dict[str, Any]:
    """
    Extrae los datos fisicos y agronomicos del invernadero asociado
    al dispositivo a traves de la relacion con la tabla invernaderos en Supabase.
    """
    try:
        # Extraer datos fisicos a traves de la relacion creada
        respuesta = (
            supabase.table("dispositivos")
            .select("id_invernadero, invernaderos(tipo_cultivo, ubicacion, area_m2)")
            .eq("id_dispositivo", id_dispositivo)
            .execute()
        )

        if respuesta.data and len(respuesta.data) > 0:
            datos_invernadero = respuesta.data[0].get("invernaderos")
            if isinstance(datos_invernadero, dict):
                return datos_invernadero
            if isinstance(datos_invernadero, list) and len(datos_invernadero) > 0 and isinstance(datos_invernadero[0], dict):
                return datos_invernadero[0]
    except Exception as e:
        logger.error("Error al extraer contexto fisico para el dispositivo %s: %s", id_dispositivo, str(e))
    return {}


def formatear_datos_para_ia(datos_crudos: list[dict[str, Any]]) -> str:
    """
    Toma un bloque cronologico de lecturas de telemetria y calcula metricas
    estadisticas y de tendencia (promedios, maximos, minimos) para proporcionar
    a la inteligencia artificial un contexto sintetizado y eficiente en consumo de tokens.
    """
    if not datos_crudos:
        return "No hay datos disponibles para el analisis."

    total_lecturas = len(datos_crudos)
    temperaturas = [float(d["temperatura"]) for d in datos_crudos if d.get("temperatura") is not None]
    humedades_amb = [float(d["humedad_ambiente"]) for d in datos_crudos if d.get("humedad_ambiente") is not None]
    humedades_suelo = [float(d["humedad_suelo"]) for d in datos_crudos if d.get("humedad_suelo") is not None]
    luces_uv = [float(d["luz_uv"]) for d in datos_crudos if d.get("luz_uv") is not None]

    temp_promedio = sum(temperaturas) / len(temperaturas) if temperaturas else 0.0
    temp_max = max(temperaturas) if temperaturas else 0.0
    temp_min = min(temperaturas) if temperaturas else 0.0

    hum_promedio = sum(humedades_amb) / len(humedades_amb) if humedades_amb else 0.0
    hum_max = max(humedades_amb) if humedades_amb else 0.0
    hum_min = min(humedades_amb) if humedades_amb else 0.0

    suelo_promedio = sum(humedades_suelo) / len(humedades_suelo) if humedades_suelo else 0.0
    suelo_min = min(humedades_suelo) if humedades_suelo else 0.0

    uv_promedio = sum(luces_uv) / len(luces_uv) if luces_uv else 0.0
    uv_max = max(luces_uv) if luces_uv else 0.0

    luces_lux = [
        float(d["intensidad_luz_lux"])
        for d in datos_crudos
        if d.get("intensidad_luz_lux") is not None
    ]
    lux_promedio = sum(luces_lux) / len(luces_lux) if luces_lux else 0.0
    lux_min = min(luces_lux) if luces_lux else 0.0

    bombas = [bool(d.get("estado_bomba")) for d in datos_crudos if d.get("estado_bomba") is not None]
    bomba_encendida = sum(1 for b in bombas if b)
    indices_calor = [
        float(d["indice_calor"])
        for d in datos_crudos
        if d.get("indice_calor") is not None
    ]
    calor_promedio = sum(indices_calor) / len(indices_calor) if indices_calor else 0.0

    resumen = (
        f"Analisis temporal de las ultimas {total_lecturas} lecturas de telemetria:\n"
        f"- Temperatura Ambiente: Promedio {temp_promedio:.1f} C (Maximo: {temp_max:.1f} C, Minimo: {temp_min:.1f} C)\n"
        f"- Humedad Relativa del Aire: Promedio {hum_promedio:.1f}% (Rango: {hum_min:.1f}% - {hum_max:.1f}%)\n"
        f"- Humedad del Sustrato / Suelo: Promedio {suelo_promedio:.1f}% (Minimo critico registrado: {suelo_min:.1f}%)\n"
        f"- Radiacion Ultravioleta (UV): Promedio {uv_promedio:.1f} (Pico maximo: {uv_max:.1f})"
    )
    if luces_lux:
        resumen += (
            f"\n- Intensidad de luz TSL2561: Promedio {lux_promedio:.0f} lux "
            f"(Minimo: {lux_min:.0f} lux)"
        )
    if indices_calor:
        resumen += f"\n- Indice de calor promedio: {calor_promedio:.1f} C"
    if bombas:
        resumen += (
            f"\n- Estado de bomba reportado: encendida en {bomba_encendida} de {len(bombas)} lecturas"
        )
    return resumen
