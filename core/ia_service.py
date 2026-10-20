import os
import json
import logging
from typing import Any
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from core.config import GEMINI_API_KEY, settings

logger = logging.getLogger(__name__)

# 1. Configurar el nuevo cliente de Google GenAI
api_key = (os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY).strip()
client: genai.Client | None = None

if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error("Error al configurar el cliente de Google GenAI: %s", str(e))
else:
    logger.warning("GEMINI_API_KEY no esta configurada en el entorno.")

# 2. Forzar la estructura de salida usando Pydantic (Nueva caracteristica de genai)
class DiagnosticoAgronomico(BaseModel):
    estado_general: str = Field(description="'OPTIMO', 'ADVERTENCIA' o 'CRITICO'")
    riesgo_detectado: str = Field(description="Nombre del riesgo o 'NINGUNO'")
    recomendacion_tecnica: str = Field(description="Instruccion breve y profesional")

def _resumir_error_ia(error: Exception) -> str:
    """Extrae un resumen conciso y legible del error sin volcar JSON crudo en la consola."""
    texto = str(error)
    if "429" in texto or "RESOURCE_EXHAUSTED" in texto:
        return "429 Cuota diaria agotada (RESOURCE_EXHAUSTED)"
    if "503" in texto or "UNAVAILABLE" in texto:
        return "503 Servicio saturado por alta demanda (UNAVAILABLE)"
    if "404" in texto or "NOT_FOUND" in texto:
        return "404 Modelo no encontrado (NOT_FOUND)"
    if "401" in texto or "403" in texto:
        return "401/403 Clave de API invalida o sin permisos"
    linea = texto.split("\n")[0]
    return linea[:90] if len(linea) > 90 else linea

def _clasificar_error_ia(error: Exception | None) -> tuple[str, str]:
    """
    Traduce las excepciones de la API de Google GenAI a mensajes limpios y comprensibles en espanol.
    Retorna una tupla: (riesgo_detectado, recomendacion_tecnica).
    """
    if not error:
        return (
            "Error de comunicacion con IA",
            "No se recibio respuesta valida del motor de inteligencia artificial.",
        )

    texto_error = str(error).upper()

    if "429" in texto_error or "RESOURCE_EXHAUSTED" in texto_error or "QUOTA" in texto_error:
        return (
            "Cuota de IA Agotada",
            "Se ha alcanzado el limite de solicitudes gratuitas de la API de Google Gemini. Por favor intente mas tarde o actualice su cuota en Google AI Studio.",
        )
    if "503" in texto_error or "UNAVAILABLE" in texto_error:
        return (
            "Servicio de IA Sobrecargado",
            "Los servidores de Google Gemini estan experimentando alta demanda temporal. Por favor, reintente en unos momentos.",
        )
    if "404" in texto_error or "NOT_FOUND" in texto_error:
        return (
            "Modelo de IA No Disponible",
            "El modelo solicitado no esta habilitado para esta cuenta en Google GenAI.",
        )
    if "401" in texto_error or "403" in texto_error or "PERMISSION_DENIED" in texto_error:
        return (
            "Credenciales de IA Invalidas",
            "La clave GEMINI_API_KEY no tiene permisos suficientes o es invalida. Verifique sus credenciales en Google AI Studio.",
        )

    return (
        "Error de Conexion con IA",
        "Ocurrio un fallo de comunicacion con el proveedor de inteligencia artificial. Verifique la conexion y disponibilidad del servicio.",
    )

def analizar_condiciones_agricolas(
    resumen_historico: str,
    cultivo: str = "Tomate"
) -> dict[str, str]:
    """
    Analiza el resumen temporal consolidado de variables microclimaticas
    utilizando el nuevo SDK de Google GenAI con salida estructurada en Pydantic.
    """
    clave_activa = (os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY).strip()
    if not client or not clave_activa:
        logger.warning("GEMINI_API_KEY no esta configurada en el entorno.")
        return {
            "estado_general": "DESCONOCIDO",
            "riesgo_detectado": "Configuracion pendiente de IA",
            "recomendacion_tecnica": "Configure la variable GEMINI_API_KEY en el entorno para habilitar analisis inteligente.",
        }

    prompt = f"""
    Eres un ingeniero agronomo experto. Analiza el siguiente historial de un invernadero cultivando {cultivo}:
    
    {resumen_historico}

    Evalua si existe algun riesgo (plagas, hongos, estres hidrico).
    """

    modelo_configurado = getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")
    candidatos = [
        modelo_configurado,
        "gemini-3.1-flash-lite",
        "gemini-flash-lite-latest",
    ]
    # Preservar orden prioritario descartando duplicados
    modelos_candidatos = list(dict.fromkeys(candidatos))

    ultimo_error: Exception | None = None

    for modelo in modelos_candidatos:
        try:
            # 3. Llamar al modelo forzando la salida estructurada
            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DiagnosticoAgronomico,
                ),
            )

            diagnostico: dict[str, Any] = json.loads(response.text)
            return {
                "estado_general": str(diagnostico.get("estado_general", "DESCONOCIDO")),
                "riesgo_detectado": str(diagnostico.get("riesgo_detectado", "NINGUNO")),
                "recomendacion_tecnica": str(diagnostico.get("recomendacion_tecnica", "Sin recomendaciones tecnicas.")),
            }
        except Exception as e:
            ultimo_error = e
            logger.warning(
                "Modelo %s no disponible (%s). Probando siguiente modelo compatible si existe...",
                modelo,
                _resumir_error_ia(e),
            )
            continue

    riesgo, recomendacion = _clasificar_error_ia(ultimo_error)
    logger.error("No se pudo completar el analisis con ningun modelo de IA: %s", _resumir_error_ia(ultimo_error))
    return {
        "estado_general": "DESCONOCIDO",
        "riesgo_detectado": riesgo,
        "recomendacion_tecnica": recomendacion,
    }