from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api.rutas_auth import router as router_auth
from api.rutas_sensores import router as router_sensores
from api.rutas_control import router as router_control

app = FastAPI(title=settings.PROJECT_NAME)

# Configuracion de CORS para comunicacion con el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de enrutadores modulares
app.include_router(router_auth)
app.include_router(router_sensores)
app.include_router(router_control)

@app.get("/", tags=["Estado"])
def estado_api() -> dict[str, str]:
    """Endpoint basico para verificacion de disponibilidad del servicio."""
    return {"status": "ok", "servicio": settings.PROJECT_NAME}