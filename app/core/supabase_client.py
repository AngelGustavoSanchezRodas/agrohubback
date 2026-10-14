from supabase import create_client, Client
from app.core.config import settings

def obtener_supabase_cliente() -> Client:
    """Crea y retorna la instancia del cliente de Supabase."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

supabase: Client = obtener_supabase_cliente()
