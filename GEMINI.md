# Reglas de Desarrollo para Modelos de IA (Antigravity / Gemini) - AgroHub Backend (Python / FastAPI)

Este documento define las directrices obligatorias, estándares de ingeniería y restricciones que cualquier agente o modelo de IA debe seguir al operar en este repositorio.

---

## 1. Prohibicion Absoluta de Emojis
- No utilizar emojis bajo ninguna circunstancia.
- Esta restriccion aplica a respuestas de chat, mensajes de commit, comentarios en el codigo, documentacion tecnica, respuestas de endpoints, mensajes de error y nombres de pruebas.
- Mantener en todo momento una comunicacion tecnica, sobria, profesional y directa.

---

## 2. Cero Alucinaciones y Verificacion Rigurosa
- Antes de proponer o modificar codigo, inspeccionar siempre los archivos reales del proyecto, sus rutas, tipos de datos y dependencias en requirements.txt y el entorno virtual.
- No asumir que una libreria, modulo, metodo o variable de entorno existe sin haber comprobado su presencia en el repositorio.
- Comprobar que el codigo no tenga errores de sintaxis o importacion (ejecutar `python -m py_compile` o pruebas unitarias con `pytest`) antes de dar por resuelta una solicitud.
- Si falta informacion o un requerimiento es ambiguo, plantear la consulta con precision tecnica en lugar de inventar o inferir comportamiento no sustentado.

---

## 3. Soluciones Definitivas (Cero Parches o Workarounds)
- Resolver siempre la causa raiz de los problemas. No aplicar soluciones provisionales, trucos superficiales ni parches rapidos.
- Prohibido suprimir advertencias o errores del analizador estatico usando directivas como `# type: ignore` o `# noqa` sin una justificacion tecnica explicita e insalvable.
- Respetar la arquitectura modular del proyecto en FastAPI:
  - `core/`: Configuracion global (`config.py`) y seguridad JWT (`security.py`).
  - `schemas/`: Definicion estricta de esquemas de datos y validacion mediante Pydantic (`telemetria.py`).
  - `api/`: Enrutadores de FastAPI divididos por dominio (`rutas_auth.py`, `rutas_sensores.py`, `rutas_control.py`).
  - `db/`: Clientes y conexion a bases de datos (`firebase_client.py`, `supabase_client.py`).
  - `main.py`: Punto de entrada que inicializa la aplicacion FastAPI, middlewares (CORS) e incluye los enrutadores.

---

## 4. Convenciones de Idioma: Uso del Espanol
- Idioma de interaccion: Todas las respuestas, explicaciones y razonamientos deben estar redactados en Espanol.
- Mensajes de error y validaciones: Excepciones lanzadas (`HTTPException(status_code=..., detail=...)`) y textos de respuesta deben redactarse en Espanol claro y formal.
- Pruebas unitarias: Las descripciones de pruebas y aserciones deben estar redactadas en Espanol.
- Comentarios y docstrings: Claros, pertinentes y redactados en Espanol.
- Identificadores de codigo: Nombres de variables, funciones y clases siguiendo la convencion de nomenclatura de Python (PEP 8: snake_case para funciones/variables, PascalCase para clases y esquemas Pydantic). Mantener coherencia en el dominio sin mezclar idiomas arbitrariamente.

---

## 5. Tipado Estricto en Python
- Utilizar anotaciones de tipo explicitas en parametros y valores de retorno de todas las funciones y endpoints.
- Evitar el uso indiscriminado de `Any`. Emplear tipos genericos (`dict[str, Any]`, `list[T]`, `Optional[T]`) o modelos Pydantic bien estructurados.
- Mantener sincronizados los esquemas de datos en `app/schemas/` ante cualquier modificacion en los contratos con el frontend o dispositivos IoT (ESP32).

---

## 6. Rigor en el Dominio AgroIoT e Integridad de Datos
- Validacion estricta de telemetria proveniente del microcontrolador ESP32 (temperatura, humedad de suelo y ambiente, radiacion, UV).
- Consistencia en la persistencia dual:
  - Firebase Realtime Database para estado inmediato y sincronizacion en tiempo real.
  - Supabase (PostgreSQL) para historico temporal de lecturas y auditoria.
- Control seguro de actuadores mediante tokens de autorizacion JWT validos.

---

## 7. Rendimiento, Dependencias y Limpieza de Codigo
- Mantener `requirements.txt` sincronizado con las dependencias efectivamente utilizadas en el proyecto.
- No dejar codigo comentado, funciones huerfanas ni declaraciones `print` de depuracion en codigo de produccion.
- Utilizar manejo estructurado de excepciones capturando errores especificos en lugar de bloques genericos silenciosos.
