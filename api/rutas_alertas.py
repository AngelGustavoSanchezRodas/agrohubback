from datetime import datetime, timezone
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from schemas.alertas import (
    AlertaAgronomicaCrear,
    AlertaAgronomicaActualizar,
    AlertaAgronomicaRespuesta,
)
from db.firebase_client import firebase_db
from db.supabase_client import supabase, asegurar_dispositivo_registrado

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alertas", tags=["Alertas Agronomicas"])

@router.get("", response_model=list[AlertaAgronomicaRespuesta])
def listar_alertas(
    id_dispositivo: str | None = Query(default=None, description="Filtrar por dispositivo emisor"),
    estado: str | None = Query(default=None, description="Filtrar por estado: ACTIVA o RESUELTA"),
    severidad: str | None = Query(default=None, description="Filtrar por severidad: BAJA, MEDIA, ALTA, CRITICA"),
    limite: int = Query(default=50, ge=1, le=200, description="Cantidad maxima de registros a devolver"),
) -> list[dict[str, Any]]:
    """
    Consulta el listado de alertas agronomicas en Supabase con opciones de filtrado.
    """
    try:
        consulta = supabase.table("alertas_agronomicas").select("*")
        if id_dispositivo:
            consulta = consulta.eq("id_dispositivo", id_dispositivo)
        if estado:
            consulta = consulta.eq("estado", estado.upper().strip())
        if severidad:
            consulta = consulta.eq("severidad", severidad.upper().strip())

        resultado = consulta.order("creado_en", desc=True).limit(limite).execute()
        return resultado.data
    except Exception as e:
        logger.error("Error al listar alertas agronomicas: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar las alertas agronomicas en Supabase",
        )

@router.get("/activas/{id_dispositivo}", response_model=list[AlertaAgronomicaRespuesta])
def obtener_alertas_activas_dispositivo(id_dispositivo: str) -> list[dict[str, Any]]:
    """
    Obtiene las alertas agronomicas activas para un dispositivo especifico.
    """
    try:
        resultado = (
            supabase.table("alertas_agronomicas")
            .select("*")
            .eq("id_dispositivo", id_dispositivo)
            .eq("estado", "ACTIVA")
            .order("creado_en", desc=True)
            .execute()
        )
        return resultado.data
    except Exception as e:
        logger.error("Error al obtener alertas activas para %s: %s", id_dispositivo, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar las alertas activas en Supabase",
        )

@router.post("", response_model=AlertaAgronomicaRespuesta, status_code=status.HTTP_201_CREATED)
def crear_alerta(alerta: AlertaAgronomicaCrear) -> dict[str, Any]:
    """
    Crea y registra una nueva alerta agronomica en Supabase y actualiza Firebase.
    """
    timestamp_actual = datetime.now(timezone.utc).isoformat()
    try:
        asegurar_dispositivo_registrado(alerta.id_dispositivo)

        payload_db = {
            "id_dispositivo": alerta.id_dispositivo,
            "tipo_riesgo": alerta.tipo_riesgo,
            "severidad": alerta.severidad.upper().strip(),
            "mensaje_diagnostico": alerta.mensaje_diagnostico,
            "estado": alerta.estado.upper().strip(),
        }

        resultado = supabase.table("alertas_agronomicas").insert(payload_db).execute()
        if not resultado.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar la alerta agronomica",
            )

        alerta_guardada = resultado.data[0]

        try:
            ref = firebase_db.reference(f"invernadero/{alerta.id_dispositivo}/ultima_alerta")
            ref.set({
                "id_alerta": alerta_guardada.get("id"),
                "tipo_riesgo": alerta.tipo_riesgo,
                "severidad": alerta.severidad.upper().strip(),
                "mensaje": alerta.mensaje_diagnostico,
                "timestamp": timestamp_actual,
            })
        except Exception as fb_err:
            logger.warning("No se pudo sincronizar alerta en Firebase: %s", str(fb_err))

        return alerta_guardada

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al crear alerta agronomica: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al registrar la alerta agronomica",
        )

@router.patch("/{id_alerta}/resolver", response_model=AlertaAgronomicaRespuesta)
def resolver_alerta(id_alerta: int) -> dict[str, Any]:
    """
    Marca una alerta agronomica como RESUELTA y asigna la fecha y hora de resolucion actual.
    """
    timestamp_resolucion = datetime.now(timezone.utc).isoformat()
    try:
        resultado = (
            supabase.table("alertas_agronomicas")
            .update({
                "estado": "RESUELTA",
                "resuelta_en": timestamp_resolucion,
            })
            .eq("id", id_alerta)
            .execute()
        )
        if not resultado.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerta con identificador {id_alerta} no encontrada",
            )

        alerta_resuelta = resultado.data[0]
        id_dispositivo = alerta_resuelta.get("id_dispositivo")
        if id_dispositivo:
            try:
                ref = firebase_db.reference(f"invernadero/{id_dispositivo}/ultima_alerta")
                ref.update({"estado": "RESUELTA", "resuelta_en": timestamp_resolucion})
            except Exception as fb_err:
                logger.warning("No se pudo actualizar estado en Firebase: %s", str(fb_err))

        return alerta_resuelta

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al resolver alerta %d: %s", id_alerta, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al resolver la alerta agronomica",
        )

@router.patch("/{id_alerta}", response_model=AlertaAgronomicaRespuesta)
def actualizar_alerta(id_alerta: int, datos: AlertaAgronomicaActualizar) -> dict[str, Any]:
    """
    Actualiza el estado y opcionalmente el mensaje diagnostico de una alerta.
    """
    try:
        estado_normalizado = datos.estado.upper().strip()
        payload_update: dict[str, Any] = {"estado": estado_normalizado}
        if estado_normalizado == "RESUELTA":
            payload_update["resuelta_en"] = datetime.now(timezone.utc).isoformat()
        elif estado_normalizado == "ACTIVA":
            payload_update["resuelta_en"] = None

        if datos.mensaje_diagnostico is not None:
            payload_update["mensaje_diagnostico"] = datos.mensaje_diagnostico

        resultado = (
            supabase.table("alertas_agronomicas")
            .update(payload_update)
            .eq("id", id_alerta)
            .execute()
        )
        if not resultado.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerta con identificador {id_alerta} no encontrada",
            )

        alerta_actualizada = resultado.data[0]
        id_dispositivo = alerta_actualizada.get("id_dispositivo")
        if id_dispositivo:
            try:
                ref = firebase_db.reference(f"invernadero/{id_dispositivo}/ultima_alerta")
                alerta_fb = ref.get()
                if isinstance(alerta_fb, dict) and (
                    alerta_fb.get("id_alerta") == id_alerta
                    or alerta_fb.get("tipo_riesgo") == alerta_actualizada.get("tipo_riesgo")
                ):
                    actualizacion_fb = {
                        "estado": estado_normalizado,
                        "mensaje": alerta_actualizada.get("mensaje_diagnostico"),
                    }
                    if estado_normalizado == "RESUELTA":
                        actualizacion_fb["resuelta_en"] = payload_update.get("resuelta_en")
                    ref.update(actualizacion_fb)
            except Exception as fb_err:
                logger.warning("No se pudo sincronizar actualizacion de alerta en Firebase: %s", str(fb_err))

        return alerta_actualizada
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al actualizar alerta %d: %s", id_alerta, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al actualizar la alerta agronomica",
        )
