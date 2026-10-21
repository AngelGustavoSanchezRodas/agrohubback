import os
from dotenv import load_dotenv

# Carga las variables del archivo .env local
load_dotenv()

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json")
FIREBASE_URL = os.getenv("FIREBASE_URL")

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Clave service_role secreta para acceso backend
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

API_KEY_SECRETA = os.getenv("API_KEY_SECRETA", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()

if not all([FIREBASE_URL, SUPABASE_URL, SUPABASE_KEY, API_KEY_SECRETA]):
    raise ValueError(
        "Faltan variables de entorno criticas para la seguridad o bases de datos. "
        "Verifique FIREBASE_URL, SUPABASE_URL, SUPABASE_KEY y API_KEY_SECRETA."
    )

if "<tu-proyecto>" in (FIREBASE_URL or "") or "<tu-id-proyecto>" in (SUPABASE_URL or ""):
    raise ValueError(
        "Configuracion invalida: FIREBASE_URL o SUPABASE_URL contienen los valores de plantilla de .env.example (<tu-proyecto>). "
        "Asegurese de configurar las variables reales en el panel de su servidor de despliegue (Render)."
    )

class Settings:
    """Carga y gestion centralizada de variables de entorno del proyecto."""
    PROJECT_NAME: str = "AgroHub Data Engine"
    FIREBASE_CREDENTIALS: str = FIREBASE_CREDENTIALS_PATH
    FIREBASE_URL: str = FIREBASE_URL
    SUPABASE_URL: str = SUPABASE_URL
    SUPABASE_KEY: str = SUPABASE_KEY
    GEMINI_API_KEY: str = GEMINI_API_KEY
    GEMINI_MODEL: str = GEMINI_MODEL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "").strip()
    
    # Seguridad de comunicacion con el frontend
    API_KEY_NOMBRE: str = "X-API-Key"
    API_KEY_SECRETA: str = API_KEY_SECRETA
    
    # Configuracion del programador hibrido de IA
    IA_SCHEDULER_HABILITADO: bool = os.getenv("IA_SCHEDULER_HABILITADO", "true").lower() in ("true", "1", "yes")
    IA_SCHEDULER_INTERVALO_MINUTOS: int = int(os.getenv("IA_SCHEDULER_INTERVALO_MINUTOS", "240"))

    # Copia el estado vivo de Firebase hacia el historial de Supabase.
    PUENTE_FIREBASE_HABILITADO: bool = os.getenv("PUENTE_FIREBASE_HABILITADO", "true").lower() in ("true", "1", "yes")
    PUENTE_FIREBASE_INTERVALO_SEGUNDOS: int = int(os.getenv("PUENTE_FIREBASE_INTERVALO_SEGUNDOS", "30"))
    FIREBASE_NODO_TELEMETRIA: str = os.getenv("FIREBASE_NODO_TELEMETRIA", "invernadero").strip()
    FIREBASE_NODO_CULTIVOS: str = os.getenv("FIREBASE_NODO_CULTIVOS", "agrohub_config/cultivos_personalizados").strip()
    # Nodos de prueba viejos que no deben alimentar historial ni alertas.
    DISPOSITIVOS_IGNORADOS: set[str] = {
        id.strip()
        for id in os.getenv("DISPOSITIVOS_IGNORADOS", "").split(",")
        if id.strip()
    }

settings = Settings()
