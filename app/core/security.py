import jwt
from typing import Any
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security = HTTPBearer()

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    """
    Middleware que intercepta la peticion y valida el token JWT.
    Si el token no es valido o expiro, bloquea el acceso al endpoint.
    """
    token = credentials.credentials
    try:
        payload: dict[str, Any] = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token de seguridad ha expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token de seguridad invalido")
