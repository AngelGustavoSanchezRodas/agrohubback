import asyncio
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status
from core.data_service import obtener_historial_reciente, formatear_datos_para_ia
from core.ia_service import analizar_condiciones_agricolas
from core.ia_scheduler import ejecutar_barrido_diagnostico_ia, estado_scheduler
from db.supabase_client import supabase, asegurar_dispositivo_registrado

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ia", tags=["Inteligencia Agrícola"])

@router.get("/diagnostico/{id_dispositivo}")
def solicitar_analisis_ia(id_dispositivo: str, cultivo: str = "Tomate") -> dict[str, Any]:
    """
    Endpoint bajo demanda (Boton en el Frontend).
    Recupera las ultimas 20 lecturas de Supabase, calcula metricas consolidadas,
    solicita un diagnostico agronomico a Google Gemini y persiste alertas si aplica.
    """
    historial = obtener_historial_reciente(id_dispositivo, limite=20)

    if not historial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El dispositivo '{id_dispositivo}' no cuenta con lecturas de telemetria en la base de datos.",
        )

    resumen_historico = formatear_datos_para_ia(historial)

    diagnostico_ia = analizar_condiciones_agricolas(
        resumen_historico=resumen_historico,
        cultivo=cultivo,
    )

    riesgo = diagnostico_ia.get("riesgo_detectado", "NINGUNO")
    estado_general = diagnostico_ia.get("estado_general", "DESCONOCIDO")

    if riesgo and riesgo.upper() != "NINGUNO" and estado_general in ["ADVERTENCIA", "CRITICO"]:
        try:
            asegurar_dispositivo_registrado(id_dispositivo)
            supabase.table("alertas_agronomicas").insert({
                "id_dispositivo": id_dispositivo,
                "tipo_riesgo": riesgo,
                "severidad": estado_general,
                "mensaje_diagnostico": diagnostico_ia.get("recomendacion_tecnica", "Sin recomendacion adicional"),
                "estado": "ACTIVA",
            }).execute()
        except Exception as e:
            logger.error("No se pudo registrar alerta de IA en base de datos para %s: %s", id_dispositivo, str(e))

    return {
        "status": "success",
        "dispositivo": id_dispositivo,
        "cultivo": cultivo,
        "contexto_analizado": resumen_historico,
        "diagnostico": diagnostico_ia,
    }

@router.post("/barrido", status_code=status.HTTP_200_OK)
async def ejecutar_barrido_manual() -> dict[str, Any]:
    """
    Ejecuta un barrido manual de diagnostico agronomico con IA sobre todos los dispositivos registrados.
    Permite gatillar el analisis global de forma manual sin esperar el siguiente ciclo programado.
    """
    if estado_scheduler.get("en_ejecucion", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un barrido de diagnostico de IA en ejecucion",
        )

    resultado = await asyncio.to_thread(ejecutar_barrido_diagnostico_ia)
    return resultado

@router.get("/programador/estado")
def consultar_estado_programador() -> dict[str, Any]:
    """
    Retorna el estado de ejecucion, configuracion de intervalo y ultimo barrido del programador de IA.
    """
    return estado_scheduler
