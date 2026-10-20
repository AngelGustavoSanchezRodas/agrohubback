from datetime import datetime
from pydantic import BaseModel, Field

class DispositivoBase(BaseModel):
    """Modelo base con atributos comunes de un dispositivo IoT."""
    id_dispositivo: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="Identificador unico del dispositivo IoT, por ejemplo: invernadero_01"
    )
    nombre: str = Field(
        ..., 
        min_length=1,
        max_length=150,
        description="Nombre descriptivo del dispositivo o estacion de monitoreo"
    )
    ubicacion: str | None = Field(
        default=None, 
        max_length=255,
        description="Ubicacion geografica o sector fisico dentro del invernadero"
    )
    estado_conexion: str = Field(
        default="INACTIVO", 
        max_length=50,
        description="Estado de conectividad del dispositivo (ACTIVO, INACTIVO, ALERTA)"
    )
    cultivo: str = Field(
        default="Tomate",
        max_length=80,
        description="Cultivo o planta asignada al invernadero para el diagnostico con IA",
    )

class DispositivoCrear(DispositivoBase):
    """Esquema para el registro formal de un nuevo dispositivo."""
    pass

class DispositivoActualizar(BaseModel):
    """Esquema para la actualizacion parcial de campos de un dispositivo."""
    nombre: str | None = Field(
        default=None, 
        min_length=1,
        max_length=150,
        description="Nuevo nombre descriptivo del dispositivo"
    )
    ubicacion: str | None = Field(
        default=None, 
        max_length=255,
        description="Nueva ubicacion del dispositivo"
    )
    estado_conexion: str | None = Field(
        default=None, 
        max_length=50,
        description="Nuevo estado de conexion (ACTIVO, INACTIVO, ALERTA)"
    )
    cultivo: str | None = Field(
        default=None,
        max_length=80,
        description="Cultivo o planta asignada al invernadero",
    )

class DispositivoRespuesta(BaseModel):
    """Esquema de respuesta detallado con datos de persistencia del dispositivo."""
    id_dispositivo: str = Field(..., description="Identificador unico del dispositivo")
    nombre: str = Field(..., description="Nombre del dispositivo")
    ubicacion: str | None = Field(default=None, description="Ubicacion del dispositivo")
    fecha_instalacion: datetime | str | None = Field(
        default=None, 
        description="Marca temporal de instalacion y alta del dispositivo"
    )
    estado_conexion: str = Field(default="INACTIVO", description="Estado de conexion actual")
    cultivo: str | None = Field(default="Tomate", description="Cultivo asignado para diagnostico IA")
