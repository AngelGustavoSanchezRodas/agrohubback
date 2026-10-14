from typing import Any
from pydantic import BaseModel, Field

class TelemetriaESP32(BaseModel):
    """Esquema de datos recibido del microcontrolador ESP32."""
    id_dispositivo: str = Field(..., description="Identificador unico del dispositivo IoT")
    temperatura: float = Field(..., description="Temperatura ambiente en grados Celsius")
    humedad_ambiente: float = Field(..., description="Porcentaje de humedad relativa ambiente")
    humedad_suelo: float = Field(..., description="Porcentaje de humedad de la tierra o sustrato")
    radiacion_solar: int = Field(..., description="Nivel de radiacion solar medido")
    luz_uv: int = Field(..., description="Indice de radiacion UV medido")

class RespuestaHistorial(BaseModel):
    """Esquema de respuesta para la consulta de telemetria historica."""
    status: str = Field(..., description="Estado de la consulta")
    total: int = Field(..., description="Cantidad total de registros devueltos")
    datos: list[dict[str, Any]] = Field(..., description="Listado de lecturas historicas")
