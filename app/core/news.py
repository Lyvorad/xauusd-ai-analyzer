"""
Módulo de noticias.

Igual que con el precio: consultamos varias fuentes en paralelo,
juntamos todo, quitamos duplicados (por título muy similar) y nos
quedamos con las más recientes y relevantes para oro/macroeconomía.
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

PALABRAS_CLAVE = [
    "gold", "oro", "fed", "federal reserve", "interest rate", "tasa de interés",
    "inflation", "inflación", "cpi", "ipc", "geopolitical", "geopolitico",
    "war", "guerra", "dollar", "dólar", "treasury", "yield",
]


@dataclass
class Noticia:
    titulo: str
    fuente: str
    fecha: datetime | None
    url: str
    sentimiento: str | None = None  # "positivo" | "negativo" | "neutral", si la API lo da


def _es_relevante(titulo: str) -> bool:
    t = titulo.lower()
    return any(palabra in t for palabra in PALABRAS_CLAVE)


def _normalizar_titulo(titulo: str) -> str:
    """Para detectar duplicados aunque el texto no sea idéntico letra por letra."""
    return re.sub(r"[^a-z0-9 ]", "", titulo.lower()).strip()


async def _marketaux(client: httpx.AsyncClient) -> list[Noticia]:
    if not settings.marketaux_api_key:
        return []
    try:
        r = await client.get(
            "https://api.marketaux.com/v1/news/all",
            params={
                "symbols": "XAU/USD",
                "filter_entities": "true",
                "language": "en",
                "api_token": settings.marketaux_api_key,
            },
        )
        data = r.json()
        noticias = []
        for item in data.get("data", []):
            noticias.append(
                Noticia(
                    titulo=item.get("title", ""),
                    fuente="marketaux",
                    fecha=_parse_fecha(item.get("published_at")),
                    url=item.get("url", ""),
                    sentimiento=item.get("sentiment"),
                )
            )
        return noticias
    except Exception:
        return []


async def _newsapi(client: httpx.AsyncClient) -> list[Noticia]:
    if not settings.newsapi_api_key:
        return []
    try:
        r = await client.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": "gold OR \"federal reserve\" OR inflation",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 15,
                "apiKey": settings.newsapi_api_key,
            },
        )
        data = r.json()
        noticias = []
        for item in data.get("articles", []):
            noticias.append(
                Noticia(
                    titulo=item.get("title", ""),
                    fuente="newsapi",
                    fecha=_parse_fecha(item.get("publishedAt")),
                    url=item.get("url", ""),
                )
            )
        return noticias
    except Exception:
        return []


async def _gnews(client: httpx.AsyncClient) -> list[Noticia]:
    if not settings.gnews_api_key:
        return []
    try:
        r = await client.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": "gold price OR federal reserve",
                "lang": "en",
                "max": 15,
                "apikey": settings.gnews_api_key,
            },
        )
        data = r.json()
        noticias = []
        for item in data.get("articles", []):
            noticias.append(
                Noticia(
                    titulo=item.get("title", ""),
                    fuente="gnews",
                    fecha=_parse_fecha(item.get("publishedAt")),
                    url=item.get("url", ""),
                )
            )
        return noticias
    except Exception:
        return []


async def _alpha_vantage_news(client: httpx.AsyncClient) -> list[Noticia]:
    """
    Ventaja de esta fuente: ya trae el sentimiento calculado (bullish/bearish/
    neutral) por Alpha Vantage, no hace falta que lo infiera Gemini.
    """
    if not settings.alpha_vantage_api_key:
        return []
    try:
        r = await client.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "topics": "financial_markets,economy_macro",
                "apikey": settings.alpha_vantage_api_key,
            },
        )
        data = r.json()
        noticias = []
        for item in data.get("feed", []):
            score = item.get("overall_sentiment_label")  # ej. "Bullish", "Bearish", "Neutral"
            noticias.append(
                Noticia(
                    titulo=item.get("title", ""),
                    fuente="alpha_vantage_news",
                    fecha=_parse_fecha_av(item.get("time_published")),
                    url=item.get("url", ""),
                    sentimiento=score,
                )
            )
        return noticias
    except Exception:
        return []


async def _finnhub_news(client: httpx.AsyncClient) -> list[Noticia]:
    if not settings.finnhub_api_key:
        return []
    try:
        r = await client.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "general", "token": settings.finnhub_api_key},
        )
        data = r.json()
        noticias = []
        for item in data[:20]:  # finnhub no pagina, recorta acá
            noticias.append(
                Noticia(
                    titulo=item.get("headline", ""),
                    fuente="finnhub_news",
                    fecha=_parse_fecha_unix(item.get("datetime")),
                    url=item.get("url", ""),
                )
            )
        return noticias
    except Exception:
        return []


def _parse_fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_fecha_av(valor: str | None) -> datetime | None:
    """Alpha Vantage devuelve fechas como '20240115T093000' (sin separadores)."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_fecha_unix(valor: int | None) -> datetime | None:
    """Finnhub devuelve timestamps Unix (segundos)."""
    if not valor:
        return None
    try:
        return datetime.fromtimestamp(valor, tz=timezone.utc)
    except Exception:
        return None


async def obtener_noticias_relevantes(max_resultado: int = 10) -> list[Noticia]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        resultados = await asyncio.gather(
            _marketaux(client),
            _newsapi(client),
            _gnews(client),
            _alpha_vantage_news(client),
            _finnhub_news(client),
        )

    todas: list[Noticia] = [n for lista in resultados for n in lista]

    # 1. Filtra solo lo relevante para oro/macro
    relevantes = [n for n in todas if _es_relevante(n.titulo)]

    # 2. Deduplica por título normalizado
    vistos = set()
    unicas = []
    for n in relevantes:
        clave = _normalizar_titulo(n.titulo)
        if clave and clave not in vistos:
            vistos.add(clave)
            unicas.append(n)

    # 3. Prioriza las más recientes (últimas 6 horas primero)
    limite = datetime.now(timezone.utc) - timedelta(hours=6)
    unicas.sort(key=lambda n: n.fecha or limite, reverse=True)

    return unicas[:max_resultado]
