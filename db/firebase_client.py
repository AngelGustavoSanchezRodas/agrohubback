import firebase_admin
from firebase_admin import credentials, db
from core.config import settings

def inicializar_firebase() -> None:
    """Inicializa la conexion con Firebase Realtime Database si no esta activa."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred, {
            "databaseURL": settings.FIREBASE_URL
        })

inicializar_firebase()

def obtener_db_referencia(ruta: str) -> db.Reference:
    """Retorna una referencia a la ruta indicada en Firebase Realtime Database."""
    return db.reference(ruta)
