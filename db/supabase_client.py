from supabase import create_client, Client
from core.config import SUPABASE_URL, SUPABASE_KEY

# Crear y exportar el cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
