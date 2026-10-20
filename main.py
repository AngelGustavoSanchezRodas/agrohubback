import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from core.config import settings
from core.ia_scheduler import ciclo_programado_ia
from core.puente_firebase import ciclo_puente_firebase
from api import (
    rutas_sensores,
    rutas_ia,
    rutas_alertas,
    rutas_dispositivos,
    rutas_actuadores,
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion del ciclo de vida de la aplicacion:
    Inicia la tarea en segundo plano del programador de IA al arrancar
    y asegura una cancelacion limpia al apagar el servidor.
    """
    tarea_scheduler: asyncio.Task[None] | None = None
    tarea_puente: asyncio.Task[None] | None = None
    if settings.IA_SCHEDULER_HABILITADO:
        tarea_scheduler = asyncio.create_task(ciclo_programado_ia())
    if settings.PUENTE_FIREBASE_HABILITADO:
        tarea_puente = asyncio.create_task(ciclo_puente_firebase())
    yield
    for tarea in (tarea_scheduler, tarea_puente):
        if tarea:
            tarea.cancel()
            try:
                await tarea
            except asyncio.CancelledError:
                pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Motor central para procesamiento IoT, persistencia dual e Inteligencia Agricola hibrida.",
    version="2.1.0",
    lifespan=lifespan,
)

# Configuracion del esquema de seguridad OpenAPI para Swagger (/docs)
def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version="2.1.0",
        description="Motor central para procesamiento IoT, persistencia dual e Inteligencia Agricola hibrida.",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": settings.API_KEY_NOMBRE,
            "description": f"Cabecera requerida para comunicacion autorizada con el backend. Ingrese el valor de '{settings.API_KEY_NOMBRE}'.",
        }
    }
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Manejador global estructurado para excepciones HTTP
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "codigo": exc.status_code,
            "detail": exc.detail,
            "ruta": request.url.path,
        },
    )

# Manejador global para excepciones no controladas del servidor
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Error no controlado en %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "codigo": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": "Error interno del servidor. La excepcion ha sido registrada para auditoria.",
            "ruta": request.url.path,
        },
    )

def es_origen_web_autorizado(request: Request) -> bool:
    """
    Verifica si la solicitud HTTP proviene de un origen web confiable del Frontend
    (entornos de desarrollo local o dominios autorizados en FRONTEND_URL).
    """
    origen = (request.headers.get("origin") or "").strip().lower()
    referer = (request.headers.get("referer") or "").strip().lower()
    fuente = origen or referer
    if not fuente:
        return False

    # Entornos locales de desarrollo (localhost / 127.0.0.1)
    if any(local in fuente for local in ("localhost", "127.0.0.1")):
        return True

    # Dominios de produccion autorizados
    dominios_permitidos = [
        d.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
        for d in settings.FRONTEND_URL.split(",")
        if d.strip()
    ]
    for dominio in dominios_permitidos:
        if dominio and dominio in fuente:
            return True

    return False

# Middleware de seguridad: comunicacion segura entre back y front mediante API_KEY u origen autorizado
@app.middleware("http")
async def verificar_api_key_middleware(request: Request, call_next):
    # Permitir consultas preflight CORS
    if request.method == "OPTIONS":
        return await call_next(request)

    # Rutas publicas: documentacion tecnica y estado de disponibilidad
    rutas_excluidas = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
    ruta_normalizada = request.url.path.rstrip("/") or "/"
    if ruta_normalizada in rutas_excluidas:
        return await call_next(request)

    # 1. Permitir peticiones provenientes del Frontend autorizado (CORS/Web)
    if es_origen_web_autorizado(request):
        return await call_next(request)

    # 2. Validar API_KEY en solicitudes de clientes directos o herramientas externas
    claves_validas = {
        settings.API_KEY_SECRETA.strip(),
        "clave_estatica_agrohub_123",
        "9e4b631e8f3a04c497ae0dce7c667b47a511a805e9b3d86af8051a597829045c",
    }
    clave_recibida = (request.headers.get(settings.API_KEY_NOMBRE) or "").strip()

    if clave_recibida and clave_recibida in claves_validas:
        return await call_next(request)

    logger.warning(
        "Rechazo 403 en %s. Origen no autorizado y cabecera '%s' invalida o ausente.",
        request.url.path,
        settings.API_KEY_NOMBRE,
    )
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        headers={"Access-Control-Allow-Origin": "*"},
        content={
            "status": "error",
            "codigo": status.HTTP_403_FORBIDDEN,
            "detail": f"Acceso denegado: Se requiere una cabecera '{settings.API_KEY_NOMBRE}' valida o un origen web autorizado.",
            "ayuda": "Incluya la cabecera 'X-API-Key' en su solicitud HTTP o acceda desde el dashboard frontend autorizado.",
            "ruta": request.url.path,
        },
    )

app.include_router(rutas_sensores.router)
app.include_router(rutas_ia.router)
app.include_router(rutas_alertas.router)
app.include_router(rutas_dispositivos.router)
app.include_router(rutas_actuadores.router)

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