import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core.cultivos import (
    CULTIVO_POR_DEFECTO,
    listar_cultivos,
    normalizar_cultivo,
    sanitizar_nombre_cultivo,
)
from core.data_service import obtener_historial_reciente, formatear_datos_para_ia
from core.ia_service import analizar_condiciones_agricolas
from core.ia_scheduler import ejecutar_barrido_diagnostico_ia, estado_scheduler
from db.firebase_client import firebase_db
from db.supabase_client import supabase, asegurar_dispositivo_registrado

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ia", tags=["Inteligencia Agrícola"])

RUTA_CULTIVOS_PERSONALIZADOS = "agrohub_config/cultivos_personalizados"


class CultivoCrear(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80, description="Nombre del cultivo o planta")


def _clave_cultivo(nombre: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", nombre.strip())
    return base.strip("_")[:80] or "cultivo"


def _leer_cultivos_personalizados() -> list[str]:
    try:
        datos = firebase_db.reference(RUTA_CULTIVOS_PERSONALIZADOS).get()
        if isinstance(datos, dict):
            nombres: list[str] = []
            for valor in datos.values():
                if isinstance(valor, dict) and valor.get("nombre"):
                    nombres.append(str(valor["nombre"]))
                elif isinstance(valor, str):
                    nombres.append(valor)
            return nombres
        if isinstance(datos, list):
            return [str(x) for x in datos if x]
    except Exception as err:
        logger.warning("No se pudieron leer cultivos personalizados: %s", str(err))
    return []


def _guardar_cultivo_personalizado(nombre: str) -> str:
    limpio = sanitizar_nombre_cultivo(nombre)
    if not limpio:
        raise ValueError("Nombre de cultivo invalido")

    clave = _clave_cultivo(limpio)
    firebase_db.reference(f"{RUTA_CULTIVOS_PERSONALIZADOS}/{clave}").set({
        "nombre": limpio,
        "creado_en": datetime.now(timezone.utc).isoformat(),
    })
    return limpio


def _obtener_cultivo_dispositivo(id_dispositivo: str) -> str:
    try:
        resultado = (
            supabase.table("dispositivos")
            .select("cultivo")
            .eq("id_dispositivo", id_dispositivo)
            .limit(1)
            .execute()
        )
        if resultado.data:
            return normalizar_cultivo(resultado.data[0].get("cultivo"))
    except Exception as err:
        logger.warning("No se pudo leer cultivo de %s: %s", id_dispositivo, str(err))
    return CULTIVO_POR_DEFECTO


def _guardar_cultivo_dispositivo(id_dispositivo: str, cultivo: str) -> None:
    cultivo_norm = normalizar_cultivo(cultivo)
    try:
        asegurar_dispositivo_registrado(id_dispositivo)
        supabase.table("dispositivos").update({
            "cultivo": cultivo_norm,
        }).eq("id_dispositivo", id_dispositivo).execute()
    except Exception as err:
        logger.warning("No se pudo guardar cultivo de %s: %s", id_dispositivo, str(err))


@router.get("/cultivos")
def consultar_cultivos_soportados() -> dict[str, Any]:
    """Lista el catalogo fijo mas los cultivos agregados por el usuario."""
    personalizados = _leer_cultivos_personalizados()
    return {
        "cultivo_por_defecto": CULTIVO_POR_DEFECTO,
        "cultivos": listar_cultivos(personalizados),
    }


@router.post("/cultivos", status_code=status.HTTP_201_CREATED)
def registrar_cultivo_personalizado(datos: CultivoCrear) -> dict[str, Any]:
    """Agrega un cultivo o planta al selector de diagnostico IA."""
    limpio = sanitizar_nombre_cultivo(datos.nombre)
    if not limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Indique un nombre de cultivo entre 2 y 80 caracteres.",
        )

    try:
        nombre = _guardar_cultivo_personalizado(limpio)
    except Exception as err:
        logger.error("Error al guardar cultivo personalizado: %s", str(err))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar el cultivo personalizado.",
        ) from err

    personalizados = _leer_cultivos_personalizados()
    return {
        "status": "success",
        "cultivo": nombre,
        "cultivos": listar_cultivos(personalizados),
    }


@router.get("/diagnostico/{id_dispositivo}")
def solicitar_analisis_ia(
    id_dispositivo: str,
    cultivo: str | None = None,
) -> dict[str, Any]:
    """
    Diagnostico bajo demanda segun el cultivo del invernadero.
    Si no se envia cultivo, usa el guardado en dispositivos o Tomate.
    """
    historial = obtener_historial_reciente(id_dispositivo, limite=20)

    if not historial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El dispositivo '{id_dispositivo}' no cuenta con lecturas de telemetria en la base de datos.",
        )

    cultivo_efectivo = normalizar_cultivo(cultivo) if cultivo else _obtener_cultivo_dispositivo(id_dispositivo)
    if cultivo:
        _guardar_cultivo_dispositivo(id_dispositivo, cultivo_efectivo)

    resumen_historico = formatear_datos_para_ia(historial)
    diagnostico_ia = analizar_condiciones_agricolas(
        resumen_historico=resumen_historico,
        cultivo=cultivo_efectivo,
    )

    try:
        firebase_db.reference(f"invernadero/{id_dispositivo}/ultimo_diagnostico_ia").set({
            **diagnostico_ia,
            "cultivo": cultivo_efectivo,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "origen": "SOLICITUD_MANUAL",
        })
    except Exception as fb_err:
        logger.warning("No se pudo guardar diagnostico en Firebase para %s: %s", id_dispositivo, str(fb_err))

    return {
        "status": "success",
        "dispositivo": id_dispositivo,
        "cultivo": cultivo_efectivo,
        "contexto_analizado": resumen_historico,
        "diagnostico": diagnostico_ia,
    }


@router.post("/barrido", status_code=status.HTTP_200_OK)
async def ejecutar_barrido_manual() -> dict[str, Any]:
    """Ejecuta un barrido manual de diagnostico sobre todos los dispositivos."""
    if estado_scheduler.get("en_ejecucion", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un barrido de diagnostico de IA en ejecucion",
        )

    resultado = await asyncio.to_thread(ejecutar_barrido_diagnostico_ia)
    return resultado


@router.get("/programador/estado")
def consultar_estado_programador() -> dict[str, Any]:
    """Estado del programador periodico de IA."""
    return estado_scheduler
