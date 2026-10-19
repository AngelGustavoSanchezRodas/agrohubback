from datetime import datetime
from pydantic import BaseModel, Field

class AlertaAgronomicaCrear(BaseModel):
    """Esquema para la creacion o reporte de una alerta agronomica."""
    id_dispositivo: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="Identificador del dispositivo IoT que origina la alerta"
    )
    tipo_riesgo: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="Clasificacion del riesgo agronomico (ESTRES_HIDRICO, GOLPE_CALOR, RIESGO_HELADA, etc.)"
    )
    severidad: str = Field(
        ..., 
        description="Nivel de severidad agronomica: BAJA, MEDIA, ALTA, CRITICA"
    )
    mensaje_diagnostico: str = Field(
        ..., 
        min_length=1,
        description="Descripcion clinica o diagnostico agronomico detallado"
    )
    estado: str = Field(
        default="ACTIVA", 
        description="Estado de la alerta: ACTIVA o RESUELTA"
    )

class AlertaAgronomicaActualizar(BaseModel):
    """Esquema para modificar el estado o resolucion de una alerta agronomica."""
    estado: str = Field(
        ..., 
        description="Nuevo estado de la alerta: ACTIVA o RESUELTA"
    )
    mensaje_diagnostico: str | None = Field(
        default=None, 
        description="Nota complementaria o actualizacion del diagnostico"
    )

class AlertaAgronomicaRespuesta(BaseModel):
    """Esquema de respuesta correspondiente a la tabla alertas_agronomicas de Supabase."""
    id: int = Field(..., description="Identificador unico de la alerta agronomica")
    id_dispositivo: str | None = Field(default=None, description="Identificador del dispositivo")
    tipo_riesgo: str = Field(..., description="Tipo de riesgo agronomo catalogado")
    severidad: str = Field(..., description="Grado de severidad de la alerta")
    mensaje_diagnostico: str = Field(..., description="Mensaje explicativo del diagnostico")
    estado: str = Field(default="ACTIVA", description="Estado operativo de la alerta")
    creado_en: datetime | str | None = Field(
        default=None, 
        description="Fecha y hora de generacion de la alerta"
    )
    resuelta_en: datetime | str | None = Field(
        default=None, 
        description="Fecha y hora de resolucion de la alerta"
    )
