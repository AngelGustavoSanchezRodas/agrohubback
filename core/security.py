import secrets
from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from core.config import settings

api_key_header = APIKeyHeader(name=settings.API_KEY_NOMBRE, auto_error=False)

def verificar_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Valida la API Key enviada en la cabecera X-API-Key para la comunicacion segura
    entre el frontend (Next.js) y el backend, utilizando comparacion en tiempo constante.
    """
    clave_esperada = settings.API_KEY_SECRETA.strip()
    if not api_key or not clave_esperada or not secrets.compare_digest(api_key.strip(), clave_esperada):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: API Key no autorizada",
        )
    return api_key
