import os
from dotenv import load_dotenv

# Carga las variables del archivo .env local
load_dotenv()

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json")
FIREBASE_URL = os.getenv("FIREBASE_URL")

SUPABASE_URL = os.getenv("SUPABASE_URL")
# CRITICO: Usar la clave SERVICE_ROLE, no la clave publica anonima
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not all([FIREBASE_URL, SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Faltan variables de entorno criticas para las bases de datos.")

class Settings:
    """Carga y gestion centralizada de variables de entorno del proyecto."""
    PROJECT_NAME: str = "AgroHub Analytics API"
    FIREBASE_CREDENTIALS: str = FIREBASE_CREDENTIALS_PATH
    FIREBASE_URL: str = FIREBASE_URL
    SUPABASE_URL: str = SUPABASE_URL
    SUPABASE_KEY: str = SUPABASE_KEY
    JWT_SECRET: str = os.getenv("JWT_SECRET", "clave_super_secreta_agrohub")
    JWT_ALGORITHM: str = "HS256"
    TOKEN_EXPIRACION_MINUTOS: int = 1440
    API_KEY_NOMBRE: str = "X-API-Key"
    API_KEY_SECRETA: str = os.getenv("API_KEY_SECRETA", "clave_estatica_agrohub_123")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "agrohubfront.vercel.app")

settings = Settings()
