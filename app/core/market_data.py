"""
Módulo de precios de XAU/USD.

Estrategia: consultamos varias APIs EN PARALELO. Cada una puede fallar
(límite alcanzado, caída del servicio, API key faltante) sin que el
sistema se detenga: simplemente se ignora esa fuente y se sigue con
las que respondieron. El precio final es la MEDIANA de las fuentes
válidas (más robusta que el promedio ante un valor atípico).
"""

import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.config import settings


@dataclass
class PrecioFuente:
    fuente: str
    precio: float | None
    error: str | None = None


@dataclass
class ConsensoPrecio:
    precio: float
    timestamp: datetime
    fuentes_usadas: list[str]
    fuentes_fallidas: list[str]
    detalle: list[PrecioFuente] = field(default_factory=list)


TIMEOUT = httpx.Timeout(8.0)


async def _twelve_data(client: httpx.AsyncClient) -> PrecioFuente:
    if not settings.twelve_data_api_key:
        return PrecioFuente("twelve_data", None, "sin API key configurada")
    try:
        r = await client.get(
            "https://api.twelvedata.com/price",
            params={"symbol": "XAU/USD", "apikey": settings.twelve_data_api_key},
        )
        data = r.json()
        if "price" not in data:
            return PrecioFuente("twelve_data", None, str(data))
        return PrecioFuente("twelve_data", float(data["price"]))
    except Exception as e:
        return PrecioFuente("twelve_data", None, str(e))


async def _alpha_vantage(client: httpx.AsyncClient) -> PrecioFuente:
    if not settings.alpha_vantage_api_key:
        return PrecioFuente("alpha_vantage", None, "sin API key configurada")
    try:
        r = await client.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": "XAU",
                "to_currency": "USD",
                "apikey": settings.alpha_vantage_api_key,
            },
        )
        data = r.json()
        rate = data.get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
        if rate is None:
            return PrecioFuente("alpha_vantage", None, str(data))
        return PrecioFuente("alpha_vantage", float(rate))
    except Exception as e:
        return PrecioFuente("alpha_vantage", None, str(e))


async def _goldapi(client: httpx.AsyncClient) -> PrecioFuente:
    if not settings.goldapi_api_key:
        return PrecioFuente("goldapi", None, "sin API key configurada")
    try:
        r = await client.get(
            "https://www.goldapi.io/api/XAU/USD",
            headers={"x-access-token": settings.goldapi_api_key},
        )
        data = r.json()
        if "price" not in data:
            return PrecioFuente("goldapi", None, str(data))
        return PrecioFuente("goldapi", float(data["price"]))
    except Exception as e:
        return PrecioFuente("goldapi", None, str(e))


async def _finnhub(client: httpx.AsyncClient) -> PrecioFuente:
    if not settings.finnhub_api_key:
        return PrecioFuente("finnhub", None, "sin API key configurada")
    try:
        # Finnhub usa el símbolo de forex OANDA:XAU_USD para spot de oro
        r = await client.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": "OANDA:XAU_USD", "token": settings.finnhub_api_key},
        )
        data = r.json()
        precio = data.get("c")  # "c" = current price
        if not precio:
            return PrecioFuente("finnhub", None, str(data))
        return PrecioFuente("finnhub", float(precio))
    except Exception as e:
        return PrecioFuente("finnhub", None, str(e))


async def obtener_precio_consenso() -> ConsensoPrecio:
    """
    Punto de entrada del módulo. Llama a todas las fuentes en paralelo,
    descarta las que fallaron y devuelve la mediana de las que sí sirvieron.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resultados = await asyncio.gather(
            _twelve_data(client),
            _alpha_vantage(client),
            _goldapi(client),
            _finnhub(client),
        )

    validos = [r for r in resultados if r.precio is not None]
    fallidos = [r for r in resultados if r.precio is None]

    if not validos:
        raise RuntimeError(
            "Ninguna fuente de precio respondió. Fuentes intentadas: "
            + ", ".join(f"{r.fuente} ({r.error})" for r in fallidos)
        )

    precios = [r.precio for r in validos]
    precio_final = statistics.median(precios)

    return ConsensoPrecio(
        precio=round(precio_final, 2),
        timestamp=datetime.now(timezone.utc),
        fuentes_usadas=[r.fuente for r in validos],
        fuentes_fallidas=[r.fuente for r in fallidos],
        detalle=resultados,
    )
