from typing import Any
from fastapi import APIRouter
from app.schemas.telemetria import TelemetriaESP32, RespuestaHistorial
from app.services.telemetria_service import (
    procesar_y_guardar_telemetria,
    consultar_historial_telemetria,
)

router = APIRouter(prefix="/api", tags=["Telemetria"])

@router.post("/telemetria")
def recibir_telemetria(datos: TelemetriaESP32) -> dict[str, str]:
    """
    Recibe lecturas de sensores emitidas por el microcontrolador ESP32
    y las persiste en Firebase y Supabase.
    """
    return procesar_y_guardar_telemetria(datos)

@router.get("/historial", response_model=RespuestaHistorial)
def obtener_historial_telemetria(limite: int = 24) -> dict[str, Any]:
    """
    Devuelve los ultimos registros de telemetria almacenados en Supabase.
    """
    return consultar_historial_telemetria(limite=limite)
