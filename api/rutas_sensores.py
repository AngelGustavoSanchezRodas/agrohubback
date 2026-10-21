from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status
from schemas.telemetria import PayloadESP32
from core.config import settings
from db.firebase_client import firebase_db
from db.supabase_client import supabase, asegurar_dispositivo_registrado
from core.data_service import obtener_historial_reciente, obtener_historial_general

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetria", tags=["Sensores"])

# El firmware enciende la bomba cuando el ADC del suelo supera 2000.
# Con seco=3000 y mojado=1200, ese punto equivale a 55.6 % de humedad.
UMBRAL_HUMEDAD_SUELO_ENCENDIDO = 55.6
UMBRAL_HUMEDAD_SUELO_APAGADO = 55.6
try:
    ZONA_INVERNADERO = ZoneInfo("America/Guatemala")
except Exception:
    ZONA_INVERNADERO = timezone(timedelta(hours=-6))
HORA_INICIO_DIA = 6
HORA_FIN_DIA = 18

def calcular_indice_calor(temperatura_c: float, humedad: float) -> float:
    """
    Calcula el indice de calor en grados Celsius a partir de la temperatura ambiente
    y la humedad relativa mediante la formula de regresion meteorologica de Rothfusz.
    Si la temperatura es menor a 26.7 C (80 F), el riesgo de calor extremo es nulo.
    """
    # Convertir a Fahrenheit para la ecuacion base
    t_f = (temperatura_c * 9.0 / 5.0) + 32.0

    # Si la temperatura es menor a 26.7 C (80 F), el riesgo de calor extremo es nulo
    if temperatura_c < 26.7:
        return round(temperatura_c, 2)

    # Formula de Rothfusz para indice de calor
    hi = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * humedad
        - 0.22475541 * t_f * humedad
        - 0.00683783 * (t_f ** 2)
        - 0.05481717 * (humedad ** 2)
        + 0.00122874 * (t_f ** 2) * humedad
        + 0.00085282 * t_f * (humedad ** 2)
        - 0.00000199 * (t_f ** 2) * (humedad ** 2)
    )

    # Retornar convertido nuevamente a Celsius
    hi_c = (hi - 32.0) * 5.0 / 9.0
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
    timestamp_resolucion = datetime.now(timezone.utc).isoformat()
    supabase.table("alertas_agronomicas").update({
        "estado": "RESUELTA",
        "resuelta_en": timestamp_resolucion,
    }).eq("id_dispositivo", id_dispositivo).eq("tipo_riesgo", tipo_riesgo).eq("estado", "ACTIVA").execute()

    try:
        ref_alerta = firebase_db.reference(f"{settings.FIREBASE_NODO_TELEMETRIA}/{id_dispositivo}/ultima_alerta")
        alerta_fb = ref_alerta.get()
        if isinstance(alerta_fb, dict) and alerta_fb.get("tipo_riesgo") == tipo_riesgo:
            ref_alerta.update({
                "estado": "RESUELTA",
                "resuelta_en": timestamp_resolucion,
            })
    except Exception as err_fb:
        logger.warning("No se pudo actualizar estado de resolucion en Firebase para %s: %s", id_dispositivo, str(err_fb))

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

                ref_alerta = firebase_db.reference(f"{settings.FIREBASE_NODO_TELEMETRIA}/{payload.id_dispositivo}/ultima_alerta")
                ref_alerta.set({
                    "tipo_riesgo": tipo_riesgo,
                    "severidad": severidad,
                    "mensaje": mensaje,
                    "estado": "ACTIVA",
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

@router.post("/sincronizar", tags=["Sensores"])
async def sincronizar_firebase_a_supabase(payload: PayloadESP32) -> dict[str, Any]:
    """
    Sincroniza y persiste telemetria del ESP32 en la tabla telemetria_historica de Supabase.
    Calcula el indice de calor agronomico y registra el historial.
    """
    try:
        asegurar_dispositivo_registrado(payload.id_dispositivo)

        # 1. Calcular campos derivados (El indice de calor no viene del ESP32)
        indice_calculado = calcular_indice_calor(
            temperatura_c=payload.temperatura, 
            humedad=payload.humedad_ambiente
        )
        
        # 2. Estructurar el diccionario exacto para la nueva tabla telemetria_historica
        datos_insercion = {
            "id_dispositivo": payload.id_dispositivo,
            "temperatura": payload.temperatura,
            "humedad_ambiente": payload.humedad_ambiente,
            "humedad_suelo": payload.humedad_suelo,
            "estado_bomba": payload.estado_bomba,
            "indice_calor": indice_calculado
        }
        
        # 3. Guardar en Supabase
        respuesta = supabase.table("telemetria_historica").insert(datos_insercion).execute()

        # 4. Evaluar alertas automaticas agronomicas
        evaluar_alertas_automaticas(payload, indice_calculado)
        
        return {
            "mensaje": "Historial sincronizado exitosamente",
            "indice_calor_registrado": indice_calculado,
            "data": respuesta.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Manejo de errores si falla la conexion a Supabase o la validacion
        logger.error("Error persistiendo datos en Supabase: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error persistiendo datos en Supabase: {str(e)}"
        )
