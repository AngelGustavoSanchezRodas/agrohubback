from typing import Any
from fastapi import APIRouter, Depends
from core.security import verificar_api_key
from schemas.telemetria import ComandoActuador, RespuestaControlActuador

router = APIRouter(prefix="/api/control", tags=["Control de Actuadores"])

@router.post("/bomba", response_model=RespuestaControlActuador)
def controlar_bomba(
    comando: ComandoActuador,
    key_validada: str = Depends(verificar_api_key),
) -> dict[str, Any]:
    """
    Endpoint protegido para controlar la bomba de agua mediante API Key.
    Requiere la cabecera X-API-Key con una clave autorizada.
    """
    estado_str = "ENCENDIDA" if comando.estado else "APAGADA"
    print(f"Comando autorizado. Bomba {estado_str}")

    return {
        "mensaje": "Orden ejecutada en el ESP32",
        "estado": comando.estado,
    }
