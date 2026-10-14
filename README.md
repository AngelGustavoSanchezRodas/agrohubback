# AgroHub Backend - API AgroIoT (Invernaderos)

Backend modular desarrollado con **FastAPI** para la ingesta, procesamiento, persistencia dual y control de actuadores para invernaderos inteligentes.

El sistema implementa una persistencia dual:
- **Firebase Realtime Database:** Almacenamiento del estado actual en tiempo real para sincronizacion instantanea con el frontend Next.js.
- **Supabase (PostgreSQL):** Almacenamiento historico de lecturas para auditoria, analitica temporal y graficas de tendencias.

---

## Requisitos Previos

Asegurate de contar con las siguientes herramientas instaladas en tu equipo:

- **Python 3.10+** (Recomendado Python 3.12 o superior)
- **Git**
- **Cuenta y proyecto en Firebase** (con servicio de Realtime Database habilitado)
- **Cuenta y proyecto en Supabase** (con base de datos PostgreSQL)

---

## Instalacion y Puesta en Marcha

Sigue estos pasos en orden para clonar el repositorio, configurar el entorno local e iniciar el servidor.

### 1. Clonar el Repositorio

Abre una terminal y clona el repositorio del backend:

```bash
git clone https://github.com/AngelGustavoSanchezRodas/agrohubback.git
cd agrohubback
```

---

### 2. Crear y Activar un Entorno Virtual

Es indispensable utilizar un entorno virtual para aislar las dependencias del proyecto y evitar conflictos con la instalacion global de Python.

#### En Windows:
```powershell
# Crear el entorno virtual
python -m venv .venv

# Activar el entorno en PowerShell
.\.venv\Scripts\Activate.ps1

# O si utilizas CMD (Simbolo del sistema):
.\.venv\Scripts\activate.bat
```

> **Nota para PowerShell:** Si la ejecucion de scripts esta deshabilitada en tu sistema, ejecuta una vez en PowerShell con permisos de administrador:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

#### En Linux / macOS:
```bash
# Crear el entorno virtual
python3 -m venv .venv

# Activar el entorno
source .venv/bin/activate
```

---

### 3. Instalar Dependencias

Con el entorno virtual activado, actualiza `pip` e instala las dependencias del proyecto:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Las dependencias principales instaladas son:
- `fastapi`: Framework web asincrono de alto rendimiento.
- `uvicorn`: Servidor ASGI para ejecucion y recarga en caliente de FastAPI.
- `firebase-admin`: SDK oficial para conectar y escribir en Firebase Realtime Database.
- `supabase`: Cliente oficial para interactuar con la base de datos PostgreSQL en Supabase.
- `python-dotenv`: Carga de variables de entorno desde el archivo `.env`.
- `pyjwt`: Generacion y validacion de tokens de seguridad JWT.

---

### 4. Configurar Variables de Entorno y Credenciales

El proyecto requiere claves y credenciales de acceso para conectarse a Firebase y Supabase.

#### A. Archivo de Variables de Entorno (`.env`)
Crea una copia del archivo `.env.example` y nombrala `.env`:

- **Windows:**
  ```powershell
  copy .env.example .env
  ```
- **Linux / macOS:**
  ```bash
  cp .env.example .env
  ```

Edita el archivo `.env` generado con tus credenciales:

```ini
# Configuracion de Firebase
FIREBASE_CREDENTIALS=firebase-credentials.json
FIREBASE_URL=https://<tu-proyecto>-default-rtdb.firebaseio.com/

# Configuracion de Supabase
SUPABASE_URL=https://<tu-id-proyecto>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu_supabase_service_role_secret_key
SUPABASE_KEY=tu_supabase_service_role_secret_key

# Configuracion de Seguridad JWT
JWT_SECRET=tu_clave_secreta_jwt_aqui

# Configuracion de API Key (Control de Actuadores)
API_KEY_SECRETA=clave_estatica_agrohub_123

# Dominio del Frontend para CORS
FRONTEND_URL=agrohubfront.vercel.app
```

#### B. Credenciales de Firebase (`firebase-credentials.json`)
1. Ve a la consola de Firebase: **Configuracion del proyecto** > **Cuentas de servicio**.
2. Haz clic en **Generar nueva clave privada**.
3. Descarga el archivo JSON y colocalo en la raiz del proyecto con el nombre:
   ```
   firebase-credentials.json
   ```

> **Importante:** Por seguridad, tanto el archivo `.env` como `firebase-credentials.json` estan incluidos en `.gitignore` y **nunca** deben subirse al repositorio.

---

### 5. Estructura de la Base de Datos (Supabase SQL)

En el panel de Supabase, accede a **SQL Editor** y ejecuta el siguiente script para inicializar las tablas necesarias con sus relaciones e integridad referencial:

```sql
-- 1. Tabla de Dispositivos (requerida por clave foranea)
create table if not exists dispositivos (
    id_dispositivo text primary key,
    nombre text,
    ubicacion text,
    creado_en timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Registrar un dispositivo inicial para pruebas de telemetria
insert into dispositivos (id_dispositivo, nombre, ubicacion)
values ('invernadero_01', 'Invernadero Principal', 'Sector Norte')
on conflict (id_dispositivo) do nothing;

-- 2. Tabla de Telemetria Historica
create table if not exists telemetria_historica (
    id bigint generated by default as identity primary key,
    creado_en timestamp with time zone default timezone('utc'::text, now()) not null,
    id_dispositivo text not null references dispositivos(id_dispositivo) on delete cascade,
    temperatura double precision,
    humedad_ambiente double precision,
    humedad_suelo double precision,
    radiacion_solar integer,
    luz_uv integer
);
```

---

### 6. Ejecutar la Aplicacion

Con el entorno virtual activado, inicia el servidor de desarrollo utilizando `uvicorn`:

```bash
uvicorn main:app --reload
```

O ejecutando directamente a traves del interprete del entorno virtual:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Para permitir conexiones desde dispositivos en la misma red local (por ejemplo, el microcontrolador ESP32 o dispositivos moviles):

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- **API Base:** `http://localhost:8000`
- **Documentacion Interactiva (Swagger UI):** `http://localhost:8000/docs`
- **Documentacion Alternativa (Redoc):** `http://localhost:8000/redoc`

---

## Endpoints de la API

### 1. Ingesta de Telemetria ESP32
Endpoint exclusivo para el microcontrolador. Actualiza el estado en tiempo real en Firebase y persiste en Supabase.

- **Metodo:** `POST`
- **Ruta:** `/api/telemetria/ingesta`
- **Cabeceras:** `Content-Type: application/json`

#### Cuerpo de la peticion (JSON):
```json
{
  "id_dispositivo": "invernadero_01",
  "temperatura": 24.5,
  "humedad_ambiente": 65.0,
  "humedad_suelo": 45.2
}
```

#### Respuesta exitosa (`200 OK`):
```json
{
  "status": "ok",
  "mensaje": "Telemetria almacenada exitosamente"
}
```

#### Ejemplo con cURL:
```bash
curl -X POST "http://localhost:8000/api/telemetria/ingesta" \
     -H "Content-Type: application/json" \
     -d '{
       "id_dispositivo": "invernadero_01",
       "temperatura": 24.5,
       "humedad_ambiente": 65.0,
       "humedad_suelo": 45.2
     }'
```

---

### 2. Consulta de Historial por Dispositivo
Endpoint para el frontend para alimentar graficas y tablas de analitica temporal.

- **Metodo:** `GET`
- **Ruta:** `/api/telemetria/historial/{id_dispositivo}?limite=50`

#### Respuesta exitosa (`200 OK`):
```json
{
  "dispositivo": "invernadero_01",
  "total_registros": 1,
  "datos": [
    {
      "id": 1,
      "id_dispositivo": "invernadero_01",
      "temperatura": 24.5,
      "humedad_ambiente": 65.0,
      "humedad_suelo": 45.2,
      "creado_en": "2026-10-14T15:00:00Z"
    }
  ]
}
```

---

### 3. Control de Actuadores (Bomba de Agua)
Endpoint protegido para emitir comandos de encendido/apagado al hardware.

- **Metodo:** `POST`
- **Ruta:** `/api/control/bomba`
- **Cabeceras:**
  - `Content-Type: application/json`
  - `X-API-Key: clave_estatica_agrohub_123`

#### Cuerpo de la peticion (JSON):
```json
{
  "estado": true
}
```

#### Respuesta exitosa (`200 OK`):
```json
{
  "mensaje": "Orden ejecutada en el ESP32",
  "estado": true
}
```

---

### 4. Autenticacion de Operadores
Endpoint para generacion de tokens de sesion JWT.

- **Metodo:** `POST`
- **Ruta:** `/api/auth/login`
- **Cabeceras:** `Content-Type: application/json`

#### Cuerpo de la peticion (JSON):
```json
{
  "usuario": "operador_01",
  "password": "tu_password_aqui"
}
```

---

## Estructura del Proyecto

```text
AgroHubBack/
├── main.py                    # Punto de entrada FastAPI y configuracion CORS
├── core/
│   ├── security.py            # Logica de seguridad (API Key y tokens JWT)
│   └── config.py              # Validacion y carga centralizada de variables .env
├── schemas/
│   └── telemetria.py          # Modelos de datos Pydantic y validacion de rangos
├── api/
│   ├── rutas_auth.py          # Endpoints de autenticacion (/api/auth)
│   ├── rutas_sensores.py      # Endpoints de telemetria e historial (/api/telemetria)
│   └── rutas_control.py       # Endpoints de control de actuadores (/api/control)
├── db/
│   ├── supabase_client.py     # Cliente de conexion a PostgreSQL en Supabase
│   └── firebase_client.py     # Cliente de conexion a Firebase Realtime Database
├── .env.example               # Plantilla de variables de entorno comentada
├── .gitignore                 # Exclusion de archivos sensibles y entornos
├── firebase-credentials.json  # Credenciales de servicio Firebase (ignorado en git)
├── GEMINI.md                  # Reglas de desarrollo y directrices de ingenieria
├── README.md                  # Guia de instalacion y documentacion tecnica
└── requirements.txt           # Dependencias del proyecto Python
```
