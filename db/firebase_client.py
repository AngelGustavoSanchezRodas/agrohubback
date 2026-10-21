import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, db
from core.config import FIREBASE_CREDENTIALS_PATH, FIREBASE_URL

logger = logging.getLogger(__name__)

# Evitar inicializar multiples veces si el modulo se recarga
if not firebase_admin._apps:
    cred = None

    # 1. Comprobar si se paso el JSON directo en una variable de entorno
    cred_json_env = os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip()
    if cred_json_env and cred_json_env.startswith("{"):
        try:
            info = json.loads(cred_json_env)
            cred = credentials.Certificate(info)
            logger.info("Firebase inicializado desde variable FIREBASE_CREDENTIALS_JSON")
        except Exception as e:
            logger.error("Error al parsear FIREBASE_CREDENTIALS_JSON: %s", str(e))

    # 2. Comprobar si FIREBASE_CREDENTIALS contiene el contenido JSON directo
    if not cred and FIREBASE_CREDENTIALS_PATH and FIREBASE_CREDENTIALS_PATH.strip().startswith("{"):
        try:
            info = json.loads(FIREBASE_CREDENTIALS_PATH.strip())
            cred = credentials.Certificate(info)
            logger.info("Firebase inicializado desde contenido JSON en FIREBASE_CREDENTIALS")
        except Exception as e:
            logger.error("Error al parsear JSON en FIREBASE_CREDENTIALS: %s", str(e))

    # 3. Comprobar rutas de archivos en disco (local o Secret Files en Render)
    if not cred:
        rutas_candidatas = [
            FIREBASE_CREDENTIALS_PATH,
            "firebase-credentials.json",
            "/etc/secrets/firebase-credentials.json",
        ]
        for ruta in rutas_candidatas:
            if ruta and os.path.isfile(ruta):
                try:
                    cred = credentials.Certificate(ruta)
                    logger.info("Firebase inicializado desde archivo: %s", ruta)
                    break
                except Exception as e:
                    logger.error("Error al cargar credenciales de Firebase desde %s: %s", ruta, str(e))

    if cred:
        try:
            firebase_admin.initialize_app(cred, {
                "databaseURL": FIREBASE_URL
            })
        except Exception as e:
            logger.error("Error al inicializar la aplicacion de Firebase: %s", str(e))
    else:
        logger.error(
            "No se pudieron cargar las credenciales de Firebase. "
            "Configure FIREBASE_CREDENTIALS_JSON o cargue el Secret File en Render."
        )

# Exportamos la instancia de la base de datos para usarla en las rutas
firebase_db = db

def obtener_db_referencia(ruta: str) -> db.Reference:
    """Retorna una referencia a la ruta indicada en Firebase Realtime Database."""
    return db.reference(ruta)
