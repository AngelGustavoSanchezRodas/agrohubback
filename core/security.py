from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader
from core.config import settings

security = HTTPBearer()
api_key_header = APIKeyHeader(name=settings.API_KEY_NOMBRE, auto_error=True)

def verificar_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Funcion validadora que verifica la API Key enviada en la cabecera X-API-Key.
    Si la clave no coincide, deniega el acceso con HTTP 403.
    """
    if api_key != settings.API_KEY_SECRETA:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado: API Key incorrecta",
        )
    return api_key

def crear_token_acceso(datos: dict[str, Any], duracion_minutos: int | None = None) -> str:
    """
    Genera un token JWT firmado con el algoritmo y clave secreta configurados.
    """
    a_codificar = datos.copy()
    tiempo_expiracion = datetime.now(timezone.utc) + timedelta(
        minutes=duracion_minutos if duracion_minutos is not None else settings.TOKEN_EXPIRACION_MINUTOS
    )
    a_codificar.update({"exp": tiempo_expiracion})
    token: str = jwt.encode(a_codificar, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    """
    Middleware de dependencia que intercepta la peticion y valida el token JWT.
    Si el token no es valido o expiro, bloquea el acceso al endpoint.
    """
    token = credentials.credentials
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token de seguridad ha expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token de seguridad invalido")
