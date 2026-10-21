import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any
from core.config import settings
from core.cultivos import CULTIVO_POR_DEFECTO, normalizar_cultivo
from core.data_service import obtener_historial_reciente, formatear_datos_para_ia
from core.ia_service import analizar_condiciones_agricolas
from db.firebase_client import firebase_db
from db.supabase_client import supabase

logger = logging.getLogger(__name__)

# Estado de auditoria en memoria del programador de IA
estado_scheduler: dict[str, Any] = {
    "activo": settings.IA_SCHEDULER_HABILITADO,
    "intervalo_minutos": settings.IA_SCHEDULER_INTERVALO_MINUTOS,
    "en_ejecucion": False,
    "total_ejecuciones": 0,
    "ultimo_barrido": None,
    "resultado_ultimo_barrido": None,
}

def ejecutar_barrido_diagnostico_ia() -> dict[str, Any]:
    """
    Ejecuta un barrido de diagnostico agronomico proactivo sobre todos los dispositivos
    registrados en Supabase. Sintetiza telemetria reciente, consulta Gemini y persiste alertas.
    """
    estado_scheduler["en_ejecucion"] = True
    inicio_ts = datetime.now(timezone.utc).isoformat()
    total_evaluados = 0
    total_alertas = 0
    detalles: list[dict[str, Any]] = []

    try:
        # 1. Obtener catalogo de dispositivos registrados
        respuesta_disp = (
            supabase.table("dispositivos")
            .select("id_dispositivo, nombre, estado_conexion, cultivo")
            .execute()
        )
        dispositivos = respuesta_disp.data or []

        if not dispositivos:
            logger.info("No hay dispositivos registrados en Supabase para el barrido de IA")
            return {
                "mensaje": "No se encontraron dispositivos registrados",
                "dispositivos_evaluados": 0,
                "alertas_emitidas": 0,
                "timestamp": inicio_ts,
            }

        for disp in dispositivos:
            id_disp = disp["id_dispositivo"]
            cultivo = normalizar_cultivo(disp.get("cultivo") or CULTIVO_POR_DEFECTO)
            total_evaluados += 1

            historial = obtener_historial_reciente(id_disp, limite=20)
            if not historial:
                logger.debug("Dispositivo %s sin telemetria reciente, omitiendo", id_disp)
                continue

            resumen_historico = formatear_datos_para_ia(historial)
            diagnostico_ia = analizar_condiciones_agricolas(
                resumen_historico=resumen_historico,
                cultivo=cultivo,
            )

            riesgo = diagnostico_ia.get("riesgo_detectado", "NINGUNO")
            estado_general = diagnostico_ia.get("estado_general", "DESCONOCIDO")

            if riesgo and riesgo.upper() != "NINGUNO" and estado_general in ["ADVERTENCIA", "CRITICO"]:
                total_alertas += 1

            try:
                ref = firebase_db.reference(f"{settings.FIREBASE_NODO_TELEMETRIA}/{id_disp}/ultimo_diagnostico_ia")
                ref.set({
                    **diagnostico_ia,
                    "cultivo": cultivo,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "origen": "TAREA_AUTOMATICA_PERIODICA",
                })
            except Exception as fb_err:
                logger.warning("No se pudo reflejar diagnostico en Firebase para %s: %s", id_disp, str(fb_err))

            detalles.append({
                "id_dispositivo": id_disp,
                "cultivo": cultivo,
                "estado_general": estado_general,
                "riesgo_detectado": riesgo,
            })

            # Pausa breve de cortesia para no saturar limites por minuto de la capa gratuita de Gemini
            time.sleep(1.5)

        resultado = {
            "mensaje": "Barrido de diagnostico con IA completado",
            "dispositivos_evaluados": total_evaluados,
            "alertas_emitidas": total_alertas,
            "timestamp": inicio_ts,
            "detalles": detalles,
        }

        estado_scheduler["total_ejecuciones"] += 1
        estado_scheduler["ultimo_barrido"] = inicio_ts
        estado_scheduler["resultado_ultimo_barrido"] = resultado
        return resultado

    except Exception as e:
        logger.error("Error durante la ejecucion del barrido de IA: %s", str(e))
        return {
            "error": str(e),
            "dispositivos_evaluados": total_evaluados,
            "alertas_emitidas": total_alertas,
            "timestamp": inicio_ts,
        }
    finally:
        estado_scheduler["en_ejecucion"] = False

async def ciclo_programado_ia() -> None:
    """
    Corutina asincrona que ejecuta periodicamente el barrido de diagnostico agronomico
    en segundo plano sin bloquear el bucle de eventos principal de FastAPI.
    """
    logger.info(
        "Programador hibrido de IA inicializado (Intervalo configurado: %d minutos)",
        settings.IA_SCHEDULER_INTERVALO_MINUTOS,
    )
    # Espera inicial de cortesia (45 segundos) para que todos los servicios esten activos tras el arranque
    await asyncio.sleep(45)

    intervalo_segundos = max(60, settings.IA_SCHEDULER_INTERVALO_MINUTOS * 60)

    while True:
        try:
            logger.info("Iniciando barrido automatico programado de IA...")
            resultado = await asyncio.to_thread(ejecutar_barrido_diagnostico_ia)
            logger.info(
                "Barrido automatico de IA finalizado: %d dispositivos evaluados, %d alertas generadas",
                resultado.get("dispositivos_evaluados", 0),
                resultado.get("alertas_emitidas", 0),
            )
        except asyncio.CancelledError:
            logger.info("Tarea en segundo plano del programador de IA cancelada correctamente")
            break
        except Exception as e:
            logger.error("Excepcion no controlada en el programador de IA: %s", str(e))

        await asyncio.sleep(intervalo_segundos)
