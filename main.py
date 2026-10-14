from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import rutas_sensores, rutas_control, rutas_auth

app = FastAPI(
    title="AgroHub Analytics API",
    description="Motor de ingesta de datos IoT y consultas analiticas",
    version="1.0.0",
)

# Permitir que el dashboard de Next.js consulte el historial y envie comandos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["FRONTEND_URL"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Acoplar los enrutadores
app.include_router(rutas_sensores.router)
app.include_router(rutas_control.router)
app.include_router(rutas_auth.router)

# Ruta retrocompatible para el frontend (/api/historial)
@app.get("/api/historial", tags=["Sensores"])
def historial_retrocompatible(limite: int = 50):
    """Ruta retrocompatible para consultas de historial general."""
    return rutas_sensores.obtener_historial_general(limite=limite)

@app.get("/", tags=["Estado"])
def estado_api() -> dict[str, str]:
    """Endpoint basico para verificacion de disponibilidad del servicio."""
    return {"status": "ok", "servicio": "AgroHub Analytics API"}