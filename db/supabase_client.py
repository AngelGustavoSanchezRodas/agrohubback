import logging
from supabase import create_client, Client
from core.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Crear y exportar el cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def asegurar_dispositivo_registrado(
    id_dispositivo: str, 
    nombre_por_defecto: str | None = None, 
    ubicacion: str | None = None
) -> None:
    """
    Verifica que el dispositivo exista en la tabla public.dispositivos.
    Si no existe, lo registra automaticamente para mantener la integridad
    referencial de claves foraneas en telemetria y alertas agronomicas.
    """
    try:
        resultado = (
            supabase.table("dispositivos")
            .select("id_dispositivo")
            .eq("id_dispositivo", id_dispositivo)
            .limit(1)
            .execute()
        )
        if not resultado.data:
            nombre = nombre_por_defecto or f"Nodo {id_dispositivo}"
            supabase.table("dispositivos").insert({
                "id_dispositivo": id_dispositivo,
                "nombre": nombre,
                "ubicacion": ubicacion or "Sector no especificado",
                "estado_conexion": "ACTIVO",
            }).execute()
            logger.info("Dispositivo %s registrado de manera automatica", id_dispositivo)
        else:
            supabase.table("dispositivos").update({
                "estado_conexion": "ACTIVO"
            }).eq("id_dispositivo", id_dispositivo).execute()
    except Exception as e:
        logger.error("Error asegurando registro del dispositivo %s: %s", id_dispositivo, str(e))
