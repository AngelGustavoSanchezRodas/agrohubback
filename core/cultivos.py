"""Catalogo de cultivos del invernadero con rangos de referencia para el diagnostico IA."""

from typing import Any

CULTIVO_POR_DEFECTO = "Tomate"

# Rangos orientativos para invernadero escolar (no sustituyen a un agronomo).
CATALOGO_CULTIVOS: dict[str, dict[str, Any]] = {
    "Tomate": {
        "descripcion": "Solanum lycopersicum en invernadero",
        "temperatura_c": (18.0, 28.0),
        "humedad_ambiente_pct": (50.0, 70.0),
        "humedad_suelo_pct": (60.0, 80.0),
        "luz_lux": (10000.0, 40000.0),
        "notas": "Evitar humedad ambiental alta prolongada (hongos). Suelo no debe secarse por debajo del umbral de riego.",
        "origen": "catalogo",
    },
    "Lechuga": {
        "descripcion": "Lactuca sativa, cultivo de hoja",
        "temperatura_c": (15.0, 22.0),
        "humedad_ambiente_pct": (50.0, 70.0),
        "humedad_suelo_pct": (65.0, 85.0),
        "luz_lux": (8000.0, 25000.0),
        "notas": "Prefiere fresco. Exceso de calor y luz intensa acelera el espigado.",
        "origen": "catalogo",
    },
    "Pimiento": {
        "descripcion": "Capsicum annuum",
        "temperatura_c": (20.0, 30.0),
        "humedad_ambiente_pct": (50.0, 70.0),
        "humedad_suelo_pct": (60.0, 80.0),
        "luz_lux": (15000.0, 45000.0),
        "notas": "Requiere buena iluminacion. Evitar encharcamiento del sustrato.",
        "origen": "catalogo",
    },
    "Fresa": {
        "descripcion": "Fragaria x ananassa",
        "temperatura_c": (15.0, 25.0),
        "humedad_ambiente_pct": (60.0, 75.0),
        "humedad_suelo_pct": (70.0, 85.0),
        "luz_lux": (10000.0, 30000.0),
        "notas": "Sustrato humedo constante sin saturacion. Humedad ambiental alta favorece Botrytis.",
        "origen": "catalogo",
    },
    "Albahaca": {
        "descripcion": "Ocimum basilicum",
        "temperatura_c": (20.0, 30.0),
        "humedad_ambiente_pct": (40.0, 60.0),
        "humedad_suelo_pct": (55.0, 75.0),
        "luz_lux": (15000.0, 40000.0),
        "notas": "Necesita luz abundante. Humedad ambiental excesiva favorece mildiu.",
        "origen": "catalogo",
    },
    "Pepino": {
        "descripcion": "Cucumis sativus",
        "temperatura_c": (22.0, 30.0),
        "humedad_ambiente_pct": (60.0, 80.0),
        "humedad_suelo_pct": (70.0, 90.0),
        "luz_lux": (15000.0, 40000.0),
        "notas": "Alta demanda hidrica. Ventilar si la humedad del aire se mantiene elevada.",
        "origen": "catalogo",
    },
}


def sanitizar_nombre_cultivo(nombre: str | None) -> str:
    """Limpia el nombre; vacio si no es usable."""
    if not nombre:
        return ""
    limpio = " ".join(str(nombre).split()).strip()
    if len(limpio) < 2 or len(limpio) > 80:
        return ""
    return limpio


def normalizar_cultivo(nombre: str | None) -> str:
    """
    Resuelve el nombre del cultivo.
    Si esta en el catalogo, usa la clave canonica.
    Si es personalizado, conserva el nombre limpio (ya no fuerza Tomate).
    """
    limpio = sanitizar_nombre_cultivo(nombre)
    if not limpio:
        return CULTIVO_POR_DEFECTO
    if limpio in CATALOGO_CULTIVOS:
        return limpio
    for id_cultivo in CATALOGO_CULTIVOS:
        if id_cultivo.lower() == limpio.lower():
            return id_cultivo
    return limpio


def es_cultivo_de_catalogo(nombre: str | None) -> bool:
    return normalizar_cultivo(nombre) in CATALOGO_CULTIVOS


def perfil_cultivo(nombre: str | None) -> dict[str, Any]:
    cultivo = normalizar_cultivo(nombre)
    if cultivo in CATALOGO_CULTIVOS:
        return {"id": cultivo, **CATALOGO_CULTIVOS[cultivo]}
    return {
        "id": cultivo,
        "descripcion": f"Cultivo personalizado: {cultivo}",
        "temperatura_c": (18.0, 28.0),
        "humedad_ambiente_pct": (45.0, 75.0),
        "humedad_suelo_pct": (55.0, 80.0),
        "luz_lux": (8000.0, 35000.0),
        "notas": (
            "Sin perfil fijo en el catalogo. Usa conocimiento agronomico general "
            f"para '{cultivo}' en invernadero y evalua humedad, luz y temperatura con criterio prudente."
        ),
        "origen": "personalizado",
    }


def listar_cultivos_catalogo() -> list[dict[str, Any]]:
    return [
        {
            "id": clave,
            "descripcion": datos["descripcion"],
            "temperatura_c": list(datos["temperatura_c"]),
            "humedad_ambiente_pct": list(datos["humedad_ambiente_pct"]),
            "humedad_suelo_pct": list(datos["humedad_suelo_pct"]),
            "luz_lux": list(datos["luz_lux"]),
            "notas": datos["notas"],
            "origen": "catalogo",
        }
        for clave, datos in CATALOGO_CULTIVOS.items()
    ]


def listar_cultivos(personalizados: list[str] | None = None) -> list[dict[str, Any]]:
    """Catalogo base + cultivos agregados por el usuario."""
    resultado = listar_cultivos_catalogo()
    vistos = {item["id"].lower() for item in resultado}
    for nombre in personalizados or []:
        limpio = sanitizar_nombre_cultivo(nombre)
        if not limpio or limpio.lower() in vistos:
            continue
        perfil = perfil_cultivo(limpio)
        resultado.append(
            {
                "id": perfil["id"],
                "descripcion": perfil["descripcion"],
                "temperatura_c": list(perfil["temperatura_c"]),
                "humedad_ambiente_pct": list(perfil["humedad_ambiente_pct"]),
                "humedad_suelo_pct": list(perfil["humedad_suelo_pct"]),
                "luz_lux": list(perfil["luz_lux"]),
                "notas": perfil["notas"],
                "origen": "personalizado",
            }
        )
        vistos.add(limpio.lower())
    return resultado


def texto_perfil_para_prompt(nombre: str | None) -> str:
    perfil = perfil_cultivo(nombre)
    t_min, t_max = perfil["temperatura_c"]
    ha_min, ha_max = perfil["humedad_ambiente_pct"]
    hs_min, hs_max = perfil["humedad_suelo_pct"]
    lux_min, lux_max = perfil["luz_lux"]
    origen = "catalogo interno" if perfil.get("origen") == "catalogo" else "cultivo personalizado"
    return (
        f"Cultivo: {perfil['id']} ({perfil['descripcion']}) [{origen}].\n"
        f"Rangos de referencia:\n"
        f"- Temperatura: {t_min:.0f}-{t_max:.0f} C\n"
        f"- Humedad del aire: {ha_min:.0f}-{ha_max:.0f} %\n"
        f"- Humedad del suelo: {hs_min:.0f}-{hs_max:.0f} %\n"
        f"- Iluminancia: {lux_min:.0f}-{lux_max:.0f} lux\n"
        f"Notas: {perfil['notas']}"
    )
