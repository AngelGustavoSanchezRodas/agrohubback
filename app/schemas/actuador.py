from pydantic import BaseModel, Field

class ComandoActuador(BaseModel):
    """Esquema de solicitud para controlar el estado de un actuador."""
    estado: bool = Field(..., description="Estado booleano deseado del actuador (True: encendido, False: apagado)")

class RespuestaControlActuador(BaseModel):
    """Esquema de respuesta tras procesar un comando de actuador."""
    mensaje: str = Field(..., description="Descripcion del resultado de la operacion")
    estado: bool = Field(..., description="Estado confirmado del actuador")
    auditoria: str = Field(..., description="Identificador del usuario que autorizo el comando")
