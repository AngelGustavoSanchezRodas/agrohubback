from datetime import datetime
from typing import Any
from fastapi import APIRouter, HTTPException
from db.firebase_client import obtener_db_referencia
from db.supabase_client import supabase
from schemas.telemetria import TelemetriaESP32, RespuestaHistorial

router = APIRouter(prefix="/api", tags=["Telemetria y Sensores"])

@router.post("/telemetria")
def recibir_telemetria(datos: TelemetriaESP32) -> dict[str, str]:
    """
    Recibe lecturas emitidas por el microcontrolador ESP32
    y las persiste en Firebase Realtime Database y en Supabase.
    """
    timestamp_actual = datetime.utcnow().isoformat()
    datos_procesados = datos.dict()
    datos_procesados["timestamp"] = timestamp_actual

    try:
        # 1. Escritura en Firebase Realtime Database (Estado en tiempo real)
        ref_estado = obtener_db_referencia(f"invernadero/{datos.id_dispositivo}/estado_actual")
        ref_estado.set(datos_procesados)

        # 2. Escritura en Supabase (Historico relacional)
        datos_supabase = {
            "id_dispositivo": datos.id_dispositivo,
            "temperatura": datos.temperatura,
            "humedad_ambiente": datos.humedad_ambiente,
            "humedad_suelo": datos.humedad_suelo,
            "radiacion_solar": datos.radiacion_solar,
            "luz_uv": datos.luz_uv,
        }
        supabase.table("telemetria_historica").insert(datos_supabase).execute()

        return {
            "mensaje": "Datos guardados en Firebase y Supabase",
            "status": "ok",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error critico en la persistencia de datos: {str(e)}",
        )

@router.get("/historial", response_model=RespuestaHistorial)
def obtener_historial_telemetria(limite: int = 24) -> dict[str, Any]:
    """
    Devuelve los ultimos registros de telemetria almacenados en Supabase.
    """
    try:
        respuesta = (
            supabase.table("telemetria_historica")
            .select("*")
            .order("creado_en", desc=True)
            .limit(limite)
            .execute()
        )
        return {
            "status": "ok",
            "total": len(respuesta.data),
            "datos": respuesta.data,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error consultando el historial en Supabase",
        )
