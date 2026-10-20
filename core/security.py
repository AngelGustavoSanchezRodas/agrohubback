from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from core.config import settings

api_key_header = APIKeyHeader(name=settings.API_KEY_NOMBRE, auto_error=False)

def verificar_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Valida la API Key enviada en la cabecera X-API-Key para la comunicacion segura
    entre el frontend (Next.js) y el backend, sin JWT ni sesiones complejas.
    """
    if api_key != settings.API_KEY_SECRETA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: API Key no autorizada",
        )
    return api_key
