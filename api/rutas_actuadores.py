from datetime import datetime, timezone
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from schemas.actuadores import (
    RegistroActuadorCrear,
    RegistroActuadorRespuesta,
)
from db.supabase_client import supabase, asegurar_dispositivo_registrado
from db.supabase_client import supabase, asegurar_dispositivo_registrado

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/actuadores", tags=["Registro de Actuadores"])

@router.get("", response_model=list[RegistroActuadorRespuesta])
def listar_registros_actuadores(
    id_dispositivo: str | None = Query(default=None, description="Filtrar por identificador de dispositivo"),
    actuador: str | None = Query(default=None, description="Filtrar por tipo de actuador (ej: BOMBA)"),
    limite: int = Query(default=50, ge=1, le=200, description="Cantidad maxima de registros a consultar"),
) -> list[dict[str, Any]]:
    """
    Consulta el historial de acciones y operaciones ejecutadas sobre actuadores en Supabase.
    """
    try:
        consulta = supabase.table("registro_actuadores").select("*")
        if id_dispositivo:
            consulta = consulta.eq("id_dispositivo", id_dispositivo)
        if actuador:
            consulta = consulta.eq("actuador", actuador.upper().strip())

        resultado = consulta.order("creado_en", desc=True).limit(limite).execute()
        return resultado.data or []
    except Exception as e:
        logger.error("Error al consultar registros de actuadores: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar el historial de actuadores en Supabase",
        )

@router.get("/historial/{id_dispositivo}", response_model=list[RegistroActuadorRespuesta])
def obtener_historial_actuadores_dispositivo(
    id_dispositivo: str,
    limite: int = Query(default=50, ge=1, le=200, description="Cantidad maxima de registros a consultar"),
) -> list[dict[str, Any]]:
    """
    Devuelve los eventos mas recientes de actuadores correspondientes a un dispositivo particular.
    """
    try:
        resultado = (
            supabase.table("registro_actuadores")
            .select("*")
            .eq("id_dispositivo", id_dispositivo)
            .order("creado_en", desc=True)
            .limit(limite)
            .execute()
        )
        return resultado.data or []
    except Exception as e:
        logger.error("Error al consultar actuadores para el dispositivo %s: %s", id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar los eventos del dispositivo en Supabase",
        )

@router.post("", response_model=RegistroActuadorRespuesta, status_code=status.HTTP_201_CREATED)
def registrar_evento_actuador(datos: RegistroActuadorCrear) -> dict[str, Any]:
    """
    Registra un evento u operacion de actuador en Supabase y sincroniza el estado en Firebase Realtime Database.
    """
    try:
        asegurar_dispositivo_registrado(datos.id_dispositivo)

        payload_db = {
            "id_dispositivo": datos.id_dispositivo,
            "actuador": datos.actuador.upper().strip(),
            "accion": datos.accion.upper().strip(),
            "origen": datos.origen.strip(),
        }
        resultado = supabase.table("registro_actuadores").insert(payload_db).execute()
        if not resultado.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar el evento del actuador en la base de datos",
            )

        return resultado.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al registrar evento de actuador para %s: %s", datos.id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al registrar el evento del actuador",
        )
