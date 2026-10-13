import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, db
from supabase import create_client, Client

# --- CARGAR VARIABLES DE ENTORNO ---
# Asegúrate de tener tu archivo .env en la misma carpeta
load_dotenv()  

# --- 1. CONFIGURACIÓN DE FIREBASE ---
cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
# Importante: Si ya tenías inicializada la app (por el reload de uvicorn), evitamos el error
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv("FIREBASE_URL")
    })

# --- 2. CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Inicializar la aplicación FastAPI
app = FastAPI(title="API AgroIoT - Invernaderos")

# Definir la estructura exacta que esperamos del ESP32 (DTO)
class TelemetriaESP32(BaseModel):
    id_dispositivo: str
    temperatura: float
    humedad_ambiente: float
    humedad_suelo: float
    radiacion_solar: int
    luz_uv: int

@app.post("/api/telemetria")
def recibir_telemetria(datos: TelemetriaESP32):
    
    timestamp_actual = datetime.utcnow().isoformat()
    datos_procesados = datos.dict()
    datos_procesados["timestamp"] = timestamp_actual
    
    # ESTE ES EL NUEVO MENSAJE QUE DEBE SALIR EN TU TERMINAL
    print(f"[{timestamp_actual}] Procesando datos de {datos.id_dispositivo}...")

    try:
        # 1. ESCRITURA EN FIREBASE (Tiempo Real)
        ref_estado = db.reference(f'invernadero/{datos.id_dispositivo}/estado_actual')
        ref_estado.set(datos_procesados)
        print("- Firebase: OK")
        
        # 2. ESCRITURA EN SUPABASE (Historial Relacional)
        datos_supabase = {
            "id_dispositivo": datos.id_dispositivo,
            "temperatura": datos.temperatura,
            "humedad_ambiente": datos.humedad_ambiente,
            "humedad_suelo": datos.humedad_suelo,
            "radiacion_solar": datos.radiacion_solar,
            "luz_uv": datos.luz_uv
        }
        
        respuesta_supabase = supabase.table('telemetria_historica').insert(datos_supabase).execute()
        print("- Supabase: OK")
        
        return {"mensaje": "Datos guardados en Firebase y Supabase", "status": "ok"}
        
    except Exception as e:
        print(f"Error crítico en la persistencia de datos: {e}")
        raise HTTPException(status_code=500, detail=str(e))