"""Modulo api: enrutadores de FastAPI para ingesta IoT, telemetria, alertas e IA."""

from api import (
    rutas_sensores,
    rutas_ia,
    rutas_alertas,
    rutas_dispositivos,
)

__all__ = [
    "rutas_sensores",
    "rutas_ia",
    "rutas_alertas",
    "rutas_dispositivos",
]
