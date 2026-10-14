import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Configuracion centralizada de variables de entorno y constantes del sistema."""
    PROJECT_NAME: str = "API AgroIoT - Invernaderos"
    FIREBASE_CREDENTIALS: str = os.getenv("FIREBASE_CREDENTIALS")
    FIREBASE_URL: str = os.getenv("FIREBASE_URL")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")
    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"

settings = Settings()
