import asyncio
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from core.config import settings
from core.ia_scheduler import ciclo_programado_ia
from api import rutas_sensores, rutas_ia, rutas_alertas, rutas_dispositivos

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion del ciclo de vida de la aplicacion:
    Inicia la tarea en segundo plano del programador de IA al arrancar
    y asegura una cancelacion limpia al apagar el servidor.
    """
    tarea_scheduler: asyncio.Task[None] | None = None
    if settings.IA_SCHEDULER_HABILITADO:
        tarea_scheduler = asyncio.create_task(ciclo_programado_ia())
    yield
    if tarea_scheduler:
        tarea_scheduler.cancel()
        try:
            await tarea_scheduler
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Motor central para procesamiento IoT, persistencia dual e Inteligencia Agricola hibrida.",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Middleware de seguridad: comunicacion segura entre back y front mediante API_KEY
@app.middleware("http")
async def verificar_api_key_middleware(request: Request, call_next):
    # Permitir consultas preflight CORS
    if request.method == "OPTIONS":
        return await call_next(request)

    # Rutas publicas: documentacion, estado de salud e ingesta directa del ESP32 en campo
    rutas_excluidas = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/telemetria/ingesta",
        "/api/telemetria",
    }
    if request.url.path in rutas_excluidas:
        return await call_next(request)

    # Validar API_KEY en la comunicacion con el frontend
    clave = request.headers.get(settings.API_KEY_NOMBRE)
    if clave != settings.API_KEY_SECRETA:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Acceso denegado: API Key no autorizada"},
        )

    return await call_next(request)

app.include_router(rutas_sensores.router)
app.include_router(rutas_ia.router)
app.include_router(rutas_alertas.router)
app.include_router(rutas_dispositivos.router)

# Ruta retrocompatible para el frontend (/api/historial)
@app.get("/api/historial", tags=["Sensores"])
def historial_retrocompatible(limite: int = 50) -> dict[str, Any]:
    """
    Ruta retrocompatible para consultas de historial general de telemetria.
    """
    return rutas_sensores.obtener_historial_general_endpoint(limite=limite)

@app.get("/", tags=["Estado"])
def estado_api() -> dict[str, str]:
    """
    Endpoint publico para verificacion de disponibilidad y estado operativo del servicio.
    """
    return {
        "status": "ok",
        "servicio": settings.PROJECT_NAME,
        "version": "2.1.0",
        "modo_ia": "hibrido (bajo demanda y programado)",
    }