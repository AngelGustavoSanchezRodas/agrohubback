import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Carga y gestion centralizada de variables de entorno del proyecto."""
    PROJECT_NAME: str = "API AgroIoT - Invernaderos"
    FIREBASE_CREDENTIALS: str = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json")
    FIREBASE_URL: str = os.getenv("FIREBASE_URL", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "clave_super_secreta_agrohub")
    JWT_ALGORITHM: str = "HS256"
    TOKEN_EXPIRACION_MINUTOS: int = 1440
    API_KEY_NOMBRE: str = "X-API-Key"
    API_KEY_SECRETA: str = os.getenv("API_KEY_SECRETA", "clave_estatica_agrohub_123")

settings = Settings()
