from datetime import datetime
from typing import Any
from fastapi import APIRouter, HTTPException
from schemas.telemetria import PayloadESP32
from db.firebase_client import firebase_db
from db.supabase_client import supabase

router = APIRouter(prefix="/api/telemetria", tags=["Sensores"])

@router.post("/ingesta")
@router.post("", include_in_schema=False)
def recibir_datos_esp32(payload: PayloadESP32) -> dict[str, str]:
    """
    Endpoint exclusivo para el hardware. 
    Recibe los datos del ESP32, actualiza el estado en vivo en Firebase y guarda el historial en Supabase.
    """
    timestamp_actual = datetime.utcnow().isoformat()
    
    try:
        # 1. Actualizar Firebase (Tiempo Real para Next.js)
        ref = firebase_db.reference(f"invernadero/{payload.id_dispositivo}/estado_actual")
        ref.set({
            "temperatura": payload.temperatura,
            "humedad_ambiente": payload.humedad_ambiente,
            "humedad_suelo": payload.humedad_suelo,
            "timestamp": timestamp_actual,
        })
        
        # 2. Guardar en Supabase (Historial Relacional)
        # Asegurarse de que el nombre de la tabla coincida con el esquema SQL
        supabase.table("telemetria_historica").insert({
            "id_dispositivo": payload.id_dispositivo,
            "temperatura": payload.temperatura,
            "humedad_ambiente": payload.humedad_ambiente,
            "humedad_suelo": payload.humedad_suelo,
        }).execute()

        return {"status": "ok", "mensaje": "Telemetria almacenada exitosamente"}

    except Exception as e:
        print(f"Error procesando telemetria: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Error interno al persistir los datos",
        )

@router.get("/historial/{id_dispositivo}")
def obtener_historial_dispositivo(id_dispositivo: str, limite: int = 50) -> dict[str, Any]:
    """
    Endpoint para el Frontend.
    Extrae los ultimos N registros de Supabase filtrados por id_dispositivo.
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
            
        return {
            "dispositivo": id_dispositivo,
            "total_registros": len(respuesta.data),
            "datos": respuesta.data,
        }
    except Exception as e:
        print(f"Error consultando historial: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Error consultando el historial de Supabase",
        )

@router.get("/historial")
def obtener_historial_general(limite: int = 50) -> dict[str, Any]:
    """
    Endpoint para consultar los ultimos registros generales de telemetria en Supabase.
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
            "total_registros": len(respuesta.data),
            "datos": respuesta.data,
        }
    except Exception as e:
        print(f"Error consultando el historial general de Supabase: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Error consultando el historial de Supabase",
        )
