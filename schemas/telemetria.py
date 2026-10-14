from typing import Any
from pydantic import BaseModel, Field

class PayloadESP32(BaseModel):
    """Esquema de telemetria recibido del microcontrolador ESP32 con validacion de rangos."""
    id_dispositivo: str = Field(
        ..., 
        description="Identificador unico del ESP32, ej: invernadero_01"
    )
    temperatura: float = Field(
        ..., 
        ge=-10.0, 
        le=80.0, 
        description="Temperatura ambiente en grados Celsius"
    )
    humedad_ambiente: float = Field(
        ..., 
        ge=0.0, 
        le=100.0, 
        description="Humedad relativa del aire en porcentaje"
    )
    humedad_suelo: float = Field(
        ..., 
        ge=0.0, 
        le=100.0, 
        description="Humedad del sustrato en porcentaje"
    )

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

class ComandoActuador(BaseModel):
    """Esquema de solicitud para controlar el estado de un actuador."""
    estado: bool = Field(..., description="Estado booleano deseado del actuador (True: encendido, False: apagado)")

class RespuestaControlActuador(BaseModel):
    """Esquema de respuesta tras procesar un comando de actuador."""
    mensaje: str = Field(..., description="Descripcion del resultado de la operacion")
    estado: bool = Field(..., description="Estado confirmado del actuador")

class SolicitudLogin(BaseModel):
    """Esquema de solicitud para inicio de sesion."""
    usuario: str = Field(..., description="Nombre de usuario o correo electronico")
    password: str = Field(..., description="Contrasena de acceso")

class RespuestaLogin(BaseModel):
    """Esquema de respuesta con token de autorizacion."""
    access_token: str = Field(..., description="Token JWT de acceso")
    token_type: str = Field("bearer", description="Tipo de token")
    usuario: str = Field(..., description="Identificador del usuario autenticado")
