import firebase_admin
from firebase_admin import credentials, db
from core.config import FIREBASE_CREDENTIALS_PATH, FIREBASE_URL

# Evitar inicializar multiples veces si el modulo se recarga
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred, {
        "databaseURL": FIREBASE_URL
    })

# Exportamos la instancia de la base de datos para usarla en las rutas
firebase_db = db

def obtener_db_referencia(ruta: str) -> db.Reference:
    """Retorna una referencia a la ruta indicada en Firebase Realtime Database."""
    return db.reference(ruta)
