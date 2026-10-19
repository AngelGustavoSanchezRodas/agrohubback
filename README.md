# AgroHub Data Engine - API AgroIoT e Inteligencia Agricola

Motor central de datos desarrollado con **FastAPI** para la ingesta robusta de telemetria IoT (microcontroladores ESP32), persistencia dual coordinada, preparacion analitica de series temporales y diagnostico agronomico asistido por inteligencia artificial con Google Gemini.

El sistema opera bajo un flujo de datos limpio y desacoplado: el hardware opera de manera independiente y autonoma en campo, mientras que el backend y el dashboard de Next.js funcionan en modalidad analitica y de solo lectura.

---

## Modelo Hibrido de Diagnostico con IA

El analisis fitosanitario opera de manera dual:
1. **Bajo Demanda:** A traves del endpoint `GET /api/ia/diagnostico/{id_dispositivo}`, invocado cuando el operador presiona el boton de analisis en el dashboard.
2. **Programado en Segundo Plano:** Una tarea asincrona (`core/ia_scheduler.py`) gestionada por el ciclo de vida de FastAPI ejecuta un barrido automatico periodico cada N minutos (por defecto 240 minutos = 4 horas), auditando todos los dispositivos registrados sin bloquear peticiones web ni saturar la cuota de Gemini.

---

## Persistencia Dual

- **Firebase Realtime Database:** Estado inmediato y telemetria en tiempo real para sincronizacion instantanea con el frontend.
- **Supabase (PostgreSQL):** Almacenamiento historico relacional de lecturas (`public.telemetria_historica`), catalogo de nodos (`public.dispositivos`) y auditoria de anomalias fitosanitarias (`public.alertas_agronomicas`).

---

## Requisitos Previos

- **Python 3.10+** (Recomendado Python 3.12 o superior)
- **Git**
- **Cuenta y proyecto en Firebase** (con Realtime Database habilitado)
- **Cuenta y proyecto en Supabase** (con base de datos PostgreSQL)
- **Clave API de Google AI Studio** (para el servicio Gemini)

---

## Instalacion y Puesta en Marcha

### 1. Clonar el Repositorio

```bash
git clone https://github.com/AngelGustavoSanchezRodas/agrohubback.git
cd agrohubback
```

---

### 2. Crear y Activar un Entorno Virtual

#### En Windows:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### En Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3. Instalar Dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### 4. Configurar Variables de Entorno (`.env`)

Crea un archivo `.env` a partir de `.env.example`:

```ini
# Configuracion de Firebase
FIREBASE_CREDENTIALS=firebase-credentials.json
FIREBASE_URL=https://<tu-proyecto>-default-rtdb.firebaseio.com/

# Configuracion de Supabase
SUPABASE_URL=https://<tu-id-proyecto>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key_aqui
SUPABASE_KEY=tu_service_role_key_aqui

# Dominio del Frontend para CORS
FRONTEND_URL=agrohubfront.vercel.app

# Inteligencia Artificial (Google Gemini)
GEMINI_API_KEY=tu_gemini_api_key_aqui

# Programador Hibrido de IA
IA_SCHEDULER_HABILITADO=true
IA_SCHEDULER_INTERVALO_MINUTOS=240
```

Coloca tu archivo de credenciales `firebase-credentials.json` en la raiz del proyecto.

---

### 5. Estructura de la Base de Datos (Supabase SQL)

En el SQL Editor de Supabase, ejecuta:

```sql
CREATE TABLE public.dispositivos (
  id_dispositivo character varying NOT NULL,
  nombre character varying NOT NULL,
  ubicacion character varying,
  fecha_instalacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  estado_conexion character varying DEFAULT 'INACTIVO'::character varying,
  CONSTRAINT dispositivos_pkey PRIMARY KEY (id_dispositivo)
);

CREATE TABLE public.telemetria_historica (
  id bigint NOT NULL DEFAULT nextval('telemetria_historica_id_seq'::regclass),
  id_dispositivo character varying,
  temperatura numeric NOT NULL,
  humedad_ambiente numeric NOT NULL,
  humedad_suelo numeric NOT NULL,
  luz_uv numeric DEFAULT 0.0,
  indice_calor numeric,
  voltaje_bateria numeric,
  creado_en timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT telemetria_historica_pkey PRIMARY KEY (id),
  CONSTRAINT telemetria_historica_id_dispositivo_fkey FOREIGN KEY (id_dispositivo) REFERENCES public.dispositivos(id_dispositivo)
);

CREATE TABLE public.alertas_agronomicas (
  id bigint NOT NULL DEFAULT nextval('alertas_agronomicas_id_seq'::regclass),
  id_dispositivo character varying,
  tipo_riesgo character varying NOT NULL,
  severidad character varying NOT NULL,
  mensaje_diagnostico text NOT NULL,
  estado character varying DEFAULT 'ACTIVA'::character varying,
  creado_en timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  resuelta_en timestamp with time zone,
  CONSTRAINT alertas_agronomicas_pkey PRIMARY KEY (id),
  CONSTRAINT alertas_agronomicas_id_dispositivo_fkey FOREIGN KEY (id_dispositivo) REFERENCES public.dispositivos(id_dispositivo)
);
```

---

### 6. Ejecutar la Aplicacion

```bash
uvicorn main:app --reload
```

- **API Base:** `http://localhost:8000`
- **Documentacion Interactiva (Swagger UI):** `http://localhost:8000/docs`

---

## Endpoints de la API

### 1. Ingesta de Telemetria (Hardware ESP32)
- **Metodo:** `POST`
- **Ruta:** `/api/telemetria/ingesta`
- **Cuerpo (JSON):**
  ```json
  {
    "id_dispositivo": "invernadero_01",
    "temperatura": 24.5,
    "humedad_ambiente": 65.0,
    "humedad_suelo": 45.2,
    "luz_uv": 2.1,
    "voltaje_bateria": 3.95
  }
  ```

### 2. Consulta de Historial (Frontend Next.js / Recharts)
- **Historial por dispositivo:** `GET /api/telemetria/historial/{id_dispositivo}?limite=50`
- **Historial general:** `GET /api/telemetria/historial?limite=50`

### 3. Diagnostico Agronomico Inteligente (Gemini IA)
- **Diagnostico bajo demanda:** `GET /api/ia/diagnostico/{id_dispositivo}?cultivo=Tomate`
- **Barrido manual de todos los nodos:** `POST /api/ia/barrido`
- **Estado del programador automatico:** `GET /api/ia/programador/estado`

### 4. Alertas y Catalogo de Dispositivos
- **Listar alertas:** `GET /api/alertas?estado=ACTIVA`
- **Alertas activas por dispositivo:** `GET /api/alertas/activas/{id_dispositivo}`
- **Listar dispositivos:** `GET /api/dispositivos`

---

## Estructura del Proyecto

```text
AgroHubBack/
├── main.py                    # Punto de entrada FastAPI, ciclo de vida lifespan y CORS
├── core/
│   ├── config.py              # Validacion y carga de variables .env
│   ├── data_service.py        # Capa de servicio de datos y pre-procesamiento estadistico
│   ├── ia_service.py          # Cliente de integracion con Google Gemini (SDK google-genai)
│   └── ia_scheduler.py        # Tarea programada en segundo plano para barrido periodico
├── schemas/
│   ├── __init__.py            # Exportacion centralizada de modelos Pydantic
│   ├── telemetria.py          # Esquemas de telemetria e ingesta ESP32
│   ├── dispositivos.py        # Esquemas para public.dispositivos
│   └── alertas.py             # Esquemas para public.alertas_agronomicas
├── api/
│   ├── __init__.py            # Modulos de enrutamiento
│   ├── rutas_sensores.py      # Endpoints de ingesta y lectura de telemetria
│   ├── rutas_ia.py            # Endpoints de diagnostico agronomico con IA
│   ├── rutas_alertas.py       # Consulta y resolucion de alertas agronomicas
│   └── rutas_dispositivos.py  # Catalogo de dispositivos IoT
├── db/
│   ├── supabase_client.py     # Cliente de base de datos Supabase
│   └── firebase_client.py     # Cliente Firebase Realtime Database
├── tests/
│   └── test_esquemas_y_logica.py # Suite de pruebas unitarias automatizadas
├── .env.example               # Plantilla de configuracion comentada
├── .gitignore                 # Exclusion de archivos sensibles
├── GEMINI.md                  # Reglas de desarrollo e ingenieria
├── README.md                  # Documentacion tecnica de la arquitectura
└── requirements.txt           # Dependencias de produccion
```

---

## Pruebas Automatizadas

```bash
python -m unittest discover tests
```
