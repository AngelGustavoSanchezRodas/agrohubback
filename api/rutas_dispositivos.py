import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status
from schemas.dispositivos import (
    DispositivoCrear,
    DispositivoActualizar,
    DispositivoRespuesta,
)
from core.cultivos import normalizar_cultivo
from db.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dispositivos", tags=["Dispositivos"])

@router.get("", response_model=list[DispositivoRespuesta])
def listar_dispositivos() -> list[dict[str, Any]]:
    """
    Lista todos los dispositivos IoT registrados en la base de datos de Supabase.
    """
    try:
        resultado = (
            supabase.table("dispositivos")
            .select("*")
            .order("id_dispositivo", desc=False)
            .execute()
        )
        return resultado.data
    except Exception as e:
        logger.error("Error al obtener listado de dispositivos: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar los dispositivos en Supabase",
        )

@router.get("/{id_dispositivo}", response_model=DispositivoRespuesta)
def obtener_dispositivo(id_dispositivo: str) -> dict[str, Any]:
    """
    Obtiene los detalles especificos de un dispositivo por su identificador unico.
    """
    try:
        resultado = (
            supabase.table("dispositivos")
            .select("*")
            .eq("id_dispositivo", id_dispositivo)
            .limit(1)
            .execute()
        )
        if not resultado.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dispositivo con identificador '{id_dispositivo}' no encontrado",
            )
        return resultado.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al obtener dispositivo %s: %s", id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar el dispositivo en Supabase",
        )

@router.post("", response_model=DispositivoRespuesta, status_code=status.HTTP_201_CREATED)
def registrar_dispositivo(datos: DispositivoCrear) -> dict[str, Any]:
    """
    Registra un nuevo dispositivo en el catalogo de public.dispositivos.
    """
    try:
        existente = (
            supabase.table("dispositivos")
            .select("id_dispositivo")
            .eq("id_dispositivo", datos.id_dispositivo)
            .limit(1)
            .execute()
        )
        if existente.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El dispositivo '{datos.id_dispositivo}' ya se encuentra registrado",
            )

        payload_db = {
            "id_dispositivo": datos.id_dispositivo,
            "nombre": datos.nombre,
            "ubicacion": datos.ubicacion,
            "estado_conexion": datos.estado_conexion,
            "cultivo": normalizar_cultivo(datos.cultivo),
        }
        resultado = supabase.table("dispositivos").insert(payload_db).execute()
        if not resultado.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar el dispositivo",
            )
        return resultado.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al registrar dispositivo %s: %s", datos.id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al registrar el dispositivo",
        )

@router.patch("/{id_dispositivo}", response_model=DispositivoRespuesta)
def actualizar_dispositivo(id_dispositivo: str, datos: DispositivoActualizar) -> dict[str, Any]:
    """
    Actualiza parcialmente los campos de un dispositivo registrado.
    """
    try:
        payload_actualizacion: dict[str, Any] = {}
        if datos.nombre is not None:
            payload_actualizacion["nombre"] = datos.nombre
        if datos.ubicacion is not None:
            payload_actualizacion["ubicacion"] = datos.ubicacion
        if datos.estado_conexion is not None:
            payload_actualizacion["estado_conexion"] = datos.estado_conexion
        if datos.cultivo is not None:
            payload_actualizacion["cultivo"] = normalizar_cultivo(datos.cultivo)

        if not payload_actualizacion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se proporcionaron campos validos para actualizar",
            )

        resultado = (
            supabase.table("dispositivos")
            .update(payload_actualizacion)
            .eq("id_dispositivo", id_dispositivo)
            .execute()
        )
        if not resultado.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dispositivo con identificador '{id_dispositivo}' no encontrado",
            )
        return resultado.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al actualizar dispositivo %s: %s", id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al actualizar el dispositivo",
        )

@router.delete("/{id_dispositivo}")
def eliminar_dispositivo(id_dispositivo: str) -> dict[str, str]:
    """
    Elimina un dispositivo del catalogo y remueve sus registros dependientes
    para salvaguardar la integridad referencial en Supabase y limpiar su estado en Firebase.
    """
    try:
        existente = (
            supabase.table("dispositivos")
            .select("id_dispositivo")
            .eq("id_dispositivo", id_dispositivo)
            .limit(1)
            .execute()
        )
        if not existente.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dispositivo con identificador '{id_dispositivo}' no encontrado",
            )

        # 1. Eliminar dependencias referenciales en Supabase
        supabase.table("registro_actuadores").delete().eq("id_dispositivo", id_dispositivo).execute()
        supabase.table("alertas_agronomicas").delete().eq("id_dispositivo", id_dispositivo).execute()
        supabase.table("telemetria_historica").delete().eq("id_dispositivo", id_dispositivo).execute()

        # 2. Eliminar el dispositivo del catalogo
        supabase.table("dispositivos").delete().eq("id_dispositivo", id_dispositivo).execute()

        # 3. Limpiar estado en Firebase Realtime Database
        try:
            from db.firebase_client import firebase_db
            firebase_db.reference(f"invernadero/{id_dispositivo}").delete()
        except Exception as fb_err:
            logger.warning("No se pudo remover nodo en Firebase para %s: %s", id_dispositivo, str(fb_err))

        return {"mensaje": f"Dispositivo '{id_dispositivo}' y sus registros asociados eliminados correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al eliminar dispositivo %s: %s", id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al eliminar el dispositivo",
        )
