from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class PayloadESP32(BaseModel):
    """Esquema de telemetria recibido del microcontrolador ESP32 con validacion estricta."""
    id_dispositivo: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="ID unico del dispositivo, ej: invernadero_01"
    )
    temperatura: float = Field(
        ..., 
        ge=-10.0, 
        le=80.0, 
        description="Temperatura en °C"
    )
    humedad_ambiente: float = Field(
        ..., 
        ge=0.0, 
        le=100.0, 
        description="Humedad relativa en %"
    )
    humedad_suelo: float = Field(
        ..., 
        ge=0.0, 
        le=100.0, 
        description="Humedad del sustrato en %"
    )
    intensidad_luz_lux: float = Field(
        default=0.0,
        ge=0.0,
        description="Iluminancia en lux proveniente del sensor TSL2561 o sensor de luz"
    )
    estado_bomba: bool = Field(
        default=False, 
        description="Estado del rele de riego"
    )

class TelemetriaESP32(BaseModel):
    """Esquema de lectura compatible con el formato historico y extendido de la tabla telemetria_historica."""
    id_dispositivo: str = Field(..., description="Identificador unico del dispositivo IoT")
    temperatura: float = Field(..., description="Temperatura ambiente en grados Celsius")
    humedad_ambiente: float = Field(..., description="Porcentaje de humedad relativa ambiente")
    humedad_suelo: float = Field(..., description="Porcentaje de humedad de la tierra o sustrato")
    luz_uv: float = Field(default=0.0, description="Indice de radiacion UV medido")
    intensidad_luz_lux: float = Field(default=0.0, description="Iluminancia del TSL2561 en lux")
    estado_bomba: bool = Field(default=False, description="Estado del rele de la bomba")
    indice_calor: float | None = Field(default=None, description="Indice de calor en grados Celsius")
    voltaje_bateria: float | None = Field(default=None, description="Voltaje de bateria en voltios")

class TelemetriaLecturaRespuesta(BaseModel):
    """Esquema representativo de un registro persistido en la tabla telemetria_historica."""
    id: int = Field(..., description="Identificador unico autoincremental de la lectura")
    id_dispositivo: str | None = Field(default=None, description="Identificador del dispositivo emisor")
    temperatura: float = Field(..., description="Temperatura registrada en grados Celsius")
    humedad_ambiente: float = Field(..., description="Humedad ambiente registrada en porcentaje")
    humedad_suelo: float = Field(..., description="Humedad de sustrato registrada en porcentaje")
    luz_uv: float = Field(default=0.0, description="Nivel de radiacion ultravioleta")
    intensidad_luz_lux: float = Field(default=0.0, description="Iluminancia registrada en lux")
    estado_bomba: bool = Field(default=False, description="Estado del rele de la bomba en esa lectura")
    indice_calor: float | None = Field(default=None, description="Indice de calor estimado o medido")
    voltaje_bateria: float | None = Field(default=None, description="Voltaje de bateria en el instante de la lectura")
    creado_en: datetime | str | None = Field(default=None, description="Marca de tiempo UTC de creacion del registro")

class RespuestaHistorial(BaseModel):
    """Esquema de respuesta para la consulta de telemetria historica."""
    status: str = Field(..., description="Estado de la consulta")
    total: int = Field(..., description="Cantidad total de registros devueltos")
    datos: list[dict[str, Any]] = Field(..., description="Listado de lecturas historicas")
