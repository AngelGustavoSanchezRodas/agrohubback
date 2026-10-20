from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status
from schemas.telemetria import PayloadESP32
from db.firebase_client import firebase_db
from db.supabase_client import supabase, asegurar_dispositivo_registrado
from core.data_service import obtener_historial_reciente, obtener_historial_general

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetria", tags=["Sensores"])

# El firmware enciende la bomba cuando el ADC del suelo supera 2000.
# Con seco=3000 y mojado=1200, ese punto equivale a 55.6 % de humedad.
UMBRAL_HUMEDAD_SUELO_ENCENDIDO = 55.6
UMBRAL_HUMEDAD_SUELO_APAGADO = 55.6
UMBRAL_LUZ_BAJA_LUX = 1000.0
ZONA_INVERNADERO = ZoneInfo("America/Guatemala")
HORA_INICIO_DIA = 6
HORA_FIN_DIA = 18

def calcular_indice_calor(temperatura_c: float, humedad_relativa: float) -> float:
    """
    Calcula el indice de calor en grados Celsius a partir de la temperatura ambiente
    y la humedad relativa mediante el algoritmo estandar de regresion meteorologica de Rothfusz.
    """
    if temperatura_c < 20.0 or humedad_relativa < 40.0:
        return round(temperatura_c, 2)

    tf = (temperatura_c * 9.0 / 5.0) + 32.0
    rh = humedad_relativa

    hi_f = 0.5 * (tf + 61.0 + ((tf - 68.0) * 1.2) + (rh * 0.094))

    if (hi_f + tf) / 2.0 >= 80.0:
        hi_f = (
            -42.379
            + 2.04901523 * tf
            + 10.14333127 * rh
            - 0.22475541 * tf * rh
            - 0.00683783 * (tf ** 2)
            - 0.05481717 * (rh ** 2)
            + 0.00122874 * (tf ** 2) * rh
            + 0.00085282 * tf * (rh ** 2)
            - 0.00000199 * (tf ** 2) * (rh ** 2)
        )

    hi_c = (hi_f - 32.0) * 5.0 / 9.0
    return round(hi_c, 2)

def es_horario_diurno(momento: datetime | None = None) -> bool:
    """El TSL2561 marca poca luz toda la noche. La alerta solo aplica de dia."""
    actual = momento or datetime.now(ZONA_INVERNADERO)
    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=ZONA_INVERNADERO)
    else:
        actual = actual.astimezone(ZONA_INVERNADERO)
    return HORA_INICIO_DIA <= actual.hour < HORA_FIN_DIA

def resolver_alerta_activa(id_dispositivo: str, tipo_riesgo: str) -> None:
    """Cierra la alerta activa cuando la condicion que la origino ya no se cumple."""
    supabase.table("alertas_agronomicas").update({
        "estado": "RESUELTA",
        "resuelta_en": datetime.now(timezone.utc).isoformat(),
    }).eq("id_dispositivo", id_dispositivo).eq("tipo_riesgo", tipo_riesgo).eq("estado", "ACTIVA").execute()

def evaluar_alertas_automaticas(payload: PayloadESP32, indice_calor: float) -> None:
    """
    Evalua umbrales criticos agronomicos y registra alertas activas si se detectan anomalias,
    evitando duplicar alertas que ya se encuentren activas en la base de datos.
    """
    alertas_detectadas: list[tuple[str, str, str]] = []

    if payload.humedad_suelo < UMBRAL_HUMEDAD_SUELO_ENCENDIDO:
        alertas_detectadas.append((
            "ESTRES_HIDRICO",
            "ALTA",
            f"Humedad de suelo en {payload.humedad_suelo}%. El Heltec enciende la bomba por debajo de {UMBRAL_HUMEDAD_SUELO_ENCENDIDO:.0f}%.",
        ))
    elif payload.humedad_suelo >= UMBRAL_HUMEDAD_SUELO_APAGADO:
        try:
            resolver_alerta_activa(payload.id_dispositivo, "ESTRES_HIDRICO")
        except Exception as err_resolver:
            logger.error("Error al resolver estres hidrico: %s", str(err_resolver))

    if payload.temperatura > 38.0 or indice_calor > 41.0:
        alertas_detectadas.append((
            "GOLPE_CALOR",
            "CRITICA",
            f"Temperatura critica de {payload.temperatura} C con indice de calor de {indice_calor} C.",
        ))
    else:
        try:
            resolver_alerta_activa(payload.id_dispositivo, "GOLPE_CALOR")
        except Exception as err_resolver:
            logger.error("Error al resolver golpe de calor: %s", str(err_resolver))

    if payload.temperatura < 4.0:
        alertas_detectadas.append((
            "RIESGO_HELADA",
            "ALTA",
            f"Temperatura de {payload.temperatura} C cercana a congelamiento. Posible necrosis celular.",
        ))
    else:
        try:
            resolver_alerta_activa(payload.id_dispositivo, "RIESGO_HELADA")
        except Exception as err_resolver:
            logger.error("Error al resolver riesgo de helada: %s", str(err_resolver))

    if payload.humedad_ambiente > 85.0 and payload.temperatura > 22.0:
        alertas_detectadas.append((
            "PROLIFERACION_HONGOS",
            "MEDIA",
            f"Humedad ambiental del {payload.humedad_ambiente}% y {payload.temperatura} C propician hongos.",
        ))
    else:
        try:
            resolver_alerta_activa(payload.id_dispositivo, "PROLIFERACION_HONGOS")
        except Exception as err_resolver:
            logger.error("Error al resolver proliferacion de hongos: %s", str(err_resolver))

    # El hardware usa TSL2561 (lux). luz_uv queda fuera de las alertas automaticas.
    if "intensidad_luz_lux" in payload.model_fields_set:
        if es_horario_diurno() and payload.intensidad_luz_lux < UMBRAL_LUZ_BAJA_LUX:
            alertas_detectadas.append((
                "LUZ_INSUFICIENTE",
                "MEDIA",
                f"Iluminancia de {payload.intensidad_luz_lux:.0f} lux durante el dia, por debajo de {UMBRAL_LUZ_BAJA_LUX:.0f} lux.",
            ))
        else:
            try:
                resolver_alerta_activa(payload.id_dispositivo, "LUZ_INSUFICIENTE")
            except Exception as err_resolver:
                logger.error("Error al resolver luz insuficiente: %s", str(err_resolver))

    if payload.voltaje_bateria is not None and payload.voltaje_bateria < 3.3:
        alertas_detectadas.append((
            "BATERIA_BAJA",
            "MEDIA",
            f"Voltaje de celda bajo ({payload.voltaje_bateria} V). Se recomienda recarga inminente.",
        ))
    elif payload.voltaje_bateria is not None:
        try:
            resolver_alerta_activa(payload.id_dispositivo, "BATERIA_BAJA")
        except Exception as err_resolver:
            logger.error("Error al resolver bateria baja: %s", str(err_resolver))

    timestamp_actual = datetime.now(timezone.utc).isoformat()

    for tipo_riesgo, severidad, mensaje in alertas_detectadas:
        try:
            existente = (
                supabase.table("alertas_agronomicas")
                .select("id")
                .eq("id_dispositivo", payload.id_dispositivo)
                .eq("tipo_riesgo", tipo_riesgo)
                .eq("estado", "ACTIVA")
                .limit(1)
                .execute()
            )
            if not existente.data:
                supabase.table("alertas_agronomicas").insert({
                    "id_dispositivo": payload.id_dispositivo,
                    "tipo_riesgo": tipo_riesgo,
                    "severidad": severidad,
                    "mensaje_diagnostico": mensaje,
                    "estado": "ACTIVA",
                }).execute()

                ref_alerta = firebase_db.reference(f"invernadero/{payload.id_dispositivo}/ultima_alerta")
                ref_alerta.set({
                    "tipo_riesgo": tipo_riesgo,
                    "severidad": severidad,
                    "mensaje": mensaje,
                    "timestamp": timestamp_actual,
                })
                logger.warning(
                    "Alerta agronomica generada para %s: %s (%s)",
                    payload.id_dispositivo,
                    tipo_riesgo,
                    severidad,
                )
        except Exception as err_alerta:
            logger.error("Error evaluando alerta agronomica %s: %s", tipo_riesgo, str(err_alerta))

@router.post("/ingesta")
@router.post("", include_in_schema=False)
def recibir_datos_esp32(payload: PayloadESP32) -> dict[str, str]:
    """
    Endpoint exclusivo para microcontroladores ESP32 y sensores IoT en campo.
    Valida la telemetria, asegura integridad en la tabla dispositivos,
    actualiza el estado en vivo en Firebase y persiste en telemetria_historica de Supabase.
    """
    timestamp_actual = datetime.now(timezone.utc).isoformat()
    indice_calor_final = payload.indice_calor
    if indice_calor_final is None:
        indice_calor_final = calcular_indice_calor(payload.temperatura, payload.humedad_ambiente)

    try:
        # 1. Asegurar registro del dispositivo para satisfacer la clave foranea
        asegurar_dispositivo_registrado(payload.id_dispositivo)

        # 2. Actualizar Firebase Realtime Database para reflejar en el frontend
        ref = firebase_db.reference(f"invernadero/{payload.id_dispositivo}/estado_actual")
        ref.set({
            "temperatura": payload.temperatura,
            "humedad_ambiente": payload.humedad_ambiente,
            "humedad_suelo": payload.humedad_suelo,
            "luz_uv": payload.luz_uv,
            "intensidad_luz_lux": payload.intensidad_luz_lux,
            "estado_bomba": payload.estado_bomba,
            "indice_calor": indice_calor_final,
            "voltaje_bateria": payload.voltaje_bateria,
            "timestamp": timestamp_actual,
        })

        # 3. Guardar en Supabase (tabla telemetria_historica)
        registro_historico = {
            "id_dispositivo": payload.id_dispositivo,
            "temperatura": payload.temperatura,
            "humedad_ambiente": payload.humedad_ambiente,
            "humedad_suelo": payload.humedad_suelo,
            "luz_uv": payload.luz_uv,
            "intensidad_luz_lux": payload.intensidad_luz_lux,
            "estado_bomba": payload.estado_bomba,
            "indice_calor": indice_calor_final,
            "voltaje_bateria": payload.voltaje_bateria,
        }
        supabase.table("telemetria_historica").insert(registro_historico).execute()

        # 4. Evaluacion automatica de alertas agronomicas
        evaluar_alertas_automaticas(payload, indice_calor_final)

        return {"status": "ok", "mensaje": "Telemetria almacenada exitosamente"}

    except Exception as e:
        logger.error("Error al procesar ingesta de telemetria para %s: %s", payload.id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al persistir la telemetria en las bases de datos",
        )

@router.get("/historial/{id_dispositivo}")
def obtener_historial_dispositivo(id_dispositivo: str, limite: int = 50) -> dict[str, Any]:
    """
    Endpoint para el Frontend (Next.js / Recharts).
    Devuelve las ultimas lecturas de telemetria delegando el acceso a data_service.
    """
    datos = obtener_historial_reciente(id_dispositivo, limite)
    return {
        "dispositivo": id_dispositivo,
        "total_registros": len(datos),
        "datos": datos,
    }

@router.get("/historial")
def obtener_historial_general_endpoint(limite: int = 50) -> dict[str, Any]:
    """
    Endpoint para consultar el historial general de telemetria desde el Frontend.
    """
    datos = obtener_historial_general(limite)
    return {
        "total_registros": len(datos),
        "datos": datos,
    }
