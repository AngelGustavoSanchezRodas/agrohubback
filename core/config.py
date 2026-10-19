import os
from dotenv import load_dotenv

# Carga las variables del archivo .env local
load_dotenv()

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json")
FIREBASE_URL = os.getenv("FIREBASE_URL")

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Clave service_role secreta para acceso backend
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if not all([FIREBASE_URL, SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Faltan variables de entorno criticas para las bases de datos.")

class Settings:
    """Carga y gestion centralizada de variables de entorno del proyecto."""
    PROJECT_NAME: str = "AgroHub Data Engine"
    FIREBASE_CREDENTIALS: str = FIREBASE_CREDENTIALS_PATH
    FIREBASE_URL: str = FIREBASE_URL
    SUPABASE_URL: str = SUPABASE_URL
    SUPABASE_KEY: str = SUPABASE_KEY
    GEMINI_API_KEY: str = GEMINI_API_KEY
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "agrohubfront.vercel.app")
    
    # Seguridad de comunicacion con el frontend
    API_KEY_NOMBRE: str = "X-API-Key"
    API_KEY_SECRETA: str = os.getenv("API_KEY_SECRETA", "clave_estatica_agrohub_123")
    
    # Configuracion del programador hibrido de IA
    IA_SCHEDULER_HABILITADO: bool = os.getenv("IA_SCHEDULER_HABILITADO", "true").lower() in ("true", "1", "yes")
    IA_SCHEDULER_INTERVALO_MINUTOS: int = int(os.getenv("IA_SCHEDULER_INTERVALO_MINUTOS", "240"))

settings = Settings()
