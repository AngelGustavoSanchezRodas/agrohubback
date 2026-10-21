import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from core.config import settings
from core.ia_scheduler import ciclo_programado_ia
from core.puente_firebase import (
    iniciar_listener_firebase,
    cerrar_listener_firebase,
)
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
    Inicia la tarea en segundo plano del programador de IA al arrancar,
    inicia la escucha en tiempo real de Firebase con el metodo listen()
    y asegura un apagado ordenado y limpio al detener el servidor.
    """
    tarea_scheduler: asyncio.Task[None] | None = None
    listener_firebase: Any = None

    if settings.IA_SCHEDULER_HABILITADO:
        tarea_scheduler = asyncio.create_task(ciclo_programado_ia())

    if settings.PUENTE_FIREBASE_HABILITADO:
        logger.info("Iniciando conexion con Firebase Realtime Database...")
        listener_firebase = iniciar_listener_firebase()

    yield

    # Acciones al apagar el servidor
    if listener_firebase is not None:
        logger.info("Cerrando listener de Firebase...")
        cerrar_listener_firebase()

    if tarea_scheduler is not None:
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

def obtener_origenes_cors(frontend_url_raw: str) -> list[str]:
    """
    Construye la lista estricta de origenes permitidos para CORS a partir de FRONTEND_URL.
    Permite entornos de desarrollo local y los dominios configurados en produccion.
    """
    origenes: set[str] = set()
    for entrada in frontend_url_raw.split(","):
        limpio = entrada.strip().rstrip("/")
        if not limpio:
            continue
        if limpio.startswith("http://") or limpio.startswith("https://"):
            origenes.add(limpio)
        else:
            origenes.add(f"https://{limpio}")
            origenes.add(f"http://{limpio}")

    # Entornos locales de desarrollo
    origenes.update([
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ])
    return sorted(list(origenes))

app.add_middleware(
    CORSMiddleware,
    allow_origins=obtener_origenes_cors(settings.FRONTEND_URL),
    allow_credentials=True,
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

# Middleware de seguridad: comunicacion segura entre front y back mediante X-API-Key obligatoria
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

    # Validacion estricta de API_KEY en cabecera mediante comparacion en tiempo constante
    clave_recibida = (request.headers.get(settings.API_KEY_NOMBRE) or "").strip()
    clave_esperada = settings.API_KEY_SECRETA.strip()

    if not clave_recibida or not clave_esperada or not secrets.compare_digest(clave_recibida, clave_esperada):
        logger.warning(
            "Rechazo 403 en %s. Cabecera '%s' invalida o ausente.",
            request.url.path,
            settings.API_KEY_NOMBRE,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "status": "error",
                "codigo": status.HTTP_403_FORBIDDEN,
                "detail": f"Acceso denegado: Se requiere una cabecera '{settings.API_KEY_NOMBRE}' valida.",
                "ruta": request.url.path,
            },
        )

    return await call_next(request)

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
        "listener_firebase": "activo" if settings.PUENTE_FIREBASE_HABILITADO else "inactivo",
    }