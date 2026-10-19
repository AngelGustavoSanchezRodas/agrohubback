"""Modulo schemas: modelos Pydantic centralizados y sincronizados con la base de datos."""

from schemas.telemetria import (
    PayloadESP32,
    TelemetriaESP32,
    TelemetriaLecturaRespuesta,
    RespuestaHistorial,
)
from schemas.dispositivos import (
    DispositivoBase,
    DispositivoCrear,
    DispositivoActualizar,
    DispositivoRespuesta,
)
from schemas.alertas import (
    AlertaAgronomicaCrear,
    AlertaAgronomicaActualizar,
    AlertaAgronomicaRespuesta,
)

__all__ = [
    "PayloadESP32",
    "TelemetriaESP32",
    "TelemetriaLecturaRespuesta",
    "RespuestaHistorial",
    "DispositivoBase",
    "DispositivoCrear",
    "DispositivoActualizar",
    "DispositivoRespuesta",
    "AlertaAgronomicaCrear",
    "AlertaAgronomicaActualizar",
    "AlertaAgronomicaRespuesta",
]
