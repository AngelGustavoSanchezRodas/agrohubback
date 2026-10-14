from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers.control import router as router_control
from app.routers.telemetria import router as router_telemetria

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
app.include_router(router_control)
app.include_router(router_telemetria)

@app.get("/", tags=["Estado"])
def estado_api() -> dict[str, str]:
    """Endpoint basico para verificacion de disponibilidad del servicio."""
    return {"status": "ok", "servicio": settings.PROJECT_NAME}