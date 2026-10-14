from typing import Any
from fastapi import APIRouter, Depends
from app.core.security import verificar_token
from app.schemas.actuador import ComandoActuador, RespuestaControlActuador
from app.services.actuador_service import ejecutar_control_bomba

router = APIRouter(prefix="/api/control", tags=["Control de Actuadores"])

@router.post("/bomba", response_model=RespuestaControlActuador)
def controlar_bomba(
    comando: ComandoActuador,
    usuario: dict[str, Any] = Depends(verificar_token),
) -> dict[str, Any]:
    """
    Endpoint protegido para encender o apagar la bomba de agua.
    Requiere autenticacion previa mediante un Bearer token JWT valido.
    """
    return ejecutar_control_bomba(comando=comando, usuario=usuario)
