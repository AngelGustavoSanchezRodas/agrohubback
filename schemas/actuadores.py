from datetime import datetime
from pydantic import BaseModel, Field

class RegistroActuadorBase(BaseModel):
    """Modelo base con atributos comunes para el registro de actuadores."""
    id_dispositivo: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identificador unico del dispositivo IoT donde opera el actuador"
    )
    actuador: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre o tipo de actuador (por ejemplo: BOMBA, VENTILADOR, VALVULA, ILUMINACION)"
    )
    accion: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Accion ejecutada en el actuador (por ejemplo: ENCENDIDO, APAGADO, ACTIVAR, DESACTIVAR)"
    )
    origen: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Origen de la accion (por ejemplo: ESP32_AUTO, MANUAL_WEB, HORARIO, IA)"
    )

class RegistroActuadorCrear(RegistroActuadorBase):
    """Esquema para crear un nuevo registro de actuador en Supabase."""
    pass

class RegistroActuadorRespuesta(BaseModel):
    """Esquema de respuesta correspondiente a la tabla public.registro_actuadores de Supabase."""
    id: int = Field(..., description="Identificador unico autoincremental del registro")
    id_dispositivo: str | None = Field(default=None, description="Identificador del dispositivo")
    actuador: str = Field(..., description="Nombre o clasificacion del actuador")
    accion: str = Field(..., description="Accion o comando ejecutado")
    origen: str = Field(..., description="Origen de la accion ejecutada")
    creado_en: datetime | str | None = Field(
        default=None,
        description="Marca temporal UTC de registro del evento"
    )
