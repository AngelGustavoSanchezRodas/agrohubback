from typing import Any
from app.schemas.actuador import ComandoActuador

def ejecutar_control_bomba(comando: ComandoActuador, usuario: dict[str, Any]) -> dict[str, Any]:
    """
    Ejecuta el control de la bomba de agua y genera el registro de auditoria del usuario.
    """
    id_usuario = usuario.get("sub", "usuario_desconocido")
    
    # Aqui se enviaria la orden al ESP32 mediante Firebase o MQTT
    
    return {
        "mensaje": "Orden procesada de forma segura",
        "estado": comando.estado,
        "auditoria": id_usuario,
    }
