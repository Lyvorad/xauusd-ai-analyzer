"""
Motor de IA. Aislado a propósito: si algún día cambian de Gemini a otro
modelo, SOLO este archivo se toca. El resto del sistema solo conoce la
función `analizar()` y el formato de salida `AnalisisIA`.
"""

import json
from dataclasses import dataclass

from google import genai
from google.genai import types

from app.config import settings
from app.core.market_data import ConsensoPrecio
from app.core.indicators import Indicadores
from app.core.news import Noticia

_cliente: genai.Client | None = None


def _obtener_cliente() -> genai.Client:
    """Creación perezosa: así el proyecto no truena al importar si todavía
    no configuraste GEMINI_API_KEY (por ejemplo, mientras pruebas otras
    partes del backend en local)."""
    global _cliente
    if _cliente is None:
        if not settings.gemini_api_key:
            raise RuntimeError("Falta GEMINI_API_KEY en el archivo .env")
        _cliente = genai.Client(api_key=settings.gemini_api_key)
    return _cliente


# Le pedimos a Gemini que devuelva EXACTAMENTE este esquema.
# Esto evita tener que parsear texto libre con regex, que es frágil.
ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "direccion": {"type": "string", "enum": ["compra", "venta", "neutral"]},
        "confianza": {"type": "integer", "description": "0 a 100"},
        "soporte": {"type": "number"},
        "resistencia": {"type": "number"},
        "resumen": {"type": "string"},
        "riesgos": {"type": "string"},
    },
    "required": ["direccion", "confianza", "soporte", "resistencia", "resumen", "riesgos"],
}

MODELO = "gemini-3.6-flash"  # rápido y económico, suficiente para este análisis


@dataclass
class AnalisisIA:
    direccion: str
    confianza: int
    soporte: float
    resistencia: float
    resumen: str
    riesgos: str


def _construir_prompt(precio: ConsensoPrecio, ind: Indicadores, noticias: list[Noticia]) -> str:
    lista_noticias = "\n".join(f"- {n.titulo} (fuente: {n.fuente})" for n in noticias) or "Sin noticias relevantes recientes."

    return f"""
Eres un analista financiero experto especializado en el mercado del oro (XAU/USD).
Analiza los siguientes datos y da tu proyección para las próximas horas.

DATOS DE MERCADO:
- Precio actual: ${precio.precio} (consenso de {len(precio.fuentes_usadas)} fuentes: {", ".join(precio.fuentes_usadas)})
- RSI (14): {ind.rsi}
- EMA 20: {ind.ema_20} | EMA 50: {ind.ema_50}
- Tendencia técnica: {ind.tendencia}
- Soporte reciente: {ind.soporte} | Resistencia reciente: {ind.resistencia}
- Volatilidad (ATR): {ind.volatilidad_atr}

NOTICIAS RECIENTES RELEVANTES:
{lista_noticias}

INSTRUCCIONES:
1. Determina la dirección más probable: "compra", "venta" o "neutral".
2. Da un nivel de confianza del 0 al 100 (sé conservador, no exageres confianza si los datos son mixtos).
3. Da niveles de soporte y resistencia claros (pueden ajustar los técnicos si las noticias lo justifican).
4. Resume en 3-4 oraciones claras el porqué de tu proyección.
5. Menciona explícitamente cualquier riesgo relevante de las noticias (ej. eventos de la Fed, alta volatilidad esperada).

Responde SOLO con el JSON solicitado, sin texto adicional.
"""


async def analizar(precio: ConsensoPrecio, ind: Indicadores, noticias: list[Noticia]) -> AnalisisIA:
    prompt = _construir_prompt(precio, ind, noticias)

    cliente = _obtener_cliente()
    respuesta = await cliente.aio.models.generate_content(
        model=MODELO,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ESQUEMA_RESPUESTA,
        ),
    )

    data = json.loads(respuesta.text)

    return AnalisisIA(
        direccion=data["direccion"],
        confianza=int(data["confianza"]),
        soporte=float(data["soporte"]),
        resistencia=float(data["resistencia"]),
        resumen=data["resumen"],
        riesgos=data["riesgos"],
    )
