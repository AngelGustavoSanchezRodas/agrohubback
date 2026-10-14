from supabase import create_client, Client
from core.config import settings

def obtener_supabase_cliente() -> Client:
    """Crea y retorna una instancia configurada del cliente Supabase."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

supabase: Client = obtener_supabase_cliente()
