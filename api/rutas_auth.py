from fastapi import APIRouter, HTTPException, status
from core.security import crear_token_acceso
from schemas.telemetria import SolicitudLogin, RespuestaLogin

router = APIRouter(prefix="/api/auth", tags=["Autenticacion"])

@router.post("/login", response_model=RespuestaLogin)
def iniciar_sesion(credenciales: SolicitudLogin) -> dict[str, str]:
    """
    Endpoint de inicio de sesion que genera y retorna un token JWT valido.
    """
    if not credenciales.usuario.strip() or not credenciales.password.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar credenciales validas",
        )

    # Generacion del token JWT con el identificador del usuario
    token_jwt = crear_token_acceso(datos={"sub": credenciales.usuario})

    return {
        "access_token": token_jwt,
        "token_type": "bearer",
        "usuario": credenciales.usuario,
    }
