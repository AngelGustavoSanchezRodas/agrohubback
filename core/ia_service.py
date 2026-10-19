import json
import logging
from typing import Any
import google.generativeai as genai
from core.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Configurar el cliente si la clave esta presente
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error("Error al configurar cliente de Gemini: %s", str(e))

def analizar_condiciones_agricolas(
    resumen_historico: str,
    cultivo: str = "Tomate"
) -> dict[str, str]:
    """
    Analiza el resumen temporal consolidado de variables microclimaticas
    utilizando el modelo Gemini 1.5 Flash y genera un diagnostico agronomico
    estructurado en formato JSON con recomendaciones tecnicas.
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY no esta configurada en el entorno.")
        return {
            "estado_general": "DESCONOCIDO",
            "riesgo_detectado": "Configuracion pendiente de IA",
            "recomendacion_tecnica": "Configure la variable GEMINI_API_KEY en el entorno para habilitar analisis inteligente.",
        }

    prompt = f"""
    Eres un ingeniero agronomo experto y asesor fitosanitario. Analiza el siguiente resumen temporal de metricas microclimaticas para un cultivo de {cultivo} en invernadero:

    {resumen_historico}

    Evalua las condiciones y determina si existe algun riesgo fitosanitario o agronomico (estres hidrico, golpe de calor, proliferacion fungica, riesgo de helada o estres por radiacion).
    Responde UNICAMENTE con un objeto JSON valido con la siguiente estructura exacta:
    {{
        "estado_general": "OPTIMO" | "ADVERTENCIA" | "CRITICO",
        "riesgo_detectado": "Nombre tecnico del riesgo o NINGUNO",
        "recomendacion_tecnica": "Instruccion tecnica profesional, concisa y aplicable"
    }}
    """

    try:
        modelo = genai.GenerativeModel("gemini-1.5-flash")
        respuesta = modelo.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        diagnostico: dict[str, Any] = json.loads(respuesta.text)
        return {
            "estado_general": str(diagnostico.get("estado_general", "DESCONOCIDO")),
            "riesgo_detectado": str(diagnostico.get("riesgo_detectado", "NINGUNO")),
            "recomendacion_tecnica": str(diagnostico.get("recomendacion_tecnica", "Sin recomendaciones tecnicas.")),
        }
    except Exception as e:
        logger.error("Error al generar diagnostico agronomico con IA: %s", str(e))
        return {
            "estado_general": "DESCONOCIDO",
            "riesgo_detectado": "Error de comunicacion con IA",
            "recomendacion_tecnica": "Revisar conectividad y cuotas de la API de diagnostico.",
        }