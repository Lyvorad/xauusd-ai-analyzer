"""
Módulo de indicadores técnicos.

A diferencia del precio "spot" (un solo número), los indicadores necesitan
una SERIE histórica de velas. Usamos Twelve Data como fuente principal para
esto porque su endpoint de time_series es gratuito y confiable; si falla,
se puede ampliar luego con otra fuente que dé velas (Finnhub también las
ofrece bajo /forex/candle).
"""

from dataclasses import dataclass

import httpx
import pandas as pd

from app.config import settings


@dataclass
class Indicadores:
    rsi: float
    ema_20: float
    ema_50: float
    tendencia: str  # "alcista" | "bajista" | "lateral"
    soporte: float
    resistencia: float
    volatilidad_atr: float


async def _obtener_velas(intervalo: str = "15min", cantidad: int = 200) -> pd.DataFrame:
    """Trae velas históricas de XAU/USD desde Twelve Data."""
    if not settings.twelve_data_api_key:
        raise RuntimeError("Se requiere TWELVE_DATA_API_KEY para calcular indicadores")

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": "XAU/USD",
                "interval": intervalo,
                "outputsize": cantidad,
                "apikey": settings.twelve_data_api_key,
            },
        )
    data = r.json()
    if "values" not in data:
        raise RuntimeError(f"No se pudo obtener histórico de velas: {data}")

    df = pd.DataFrame(data["values"])
    df = df.rename(columns={"datetime": "fecha"})
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha").reset_index(drop=True)  # la API la da del más nuevo al más viejo
    return df


def _calcular_rsi(cierre: pd.Series, periodo: int = 14) -> float:
    delta = cierre.diff()
    ganancia = delta.clip(lower=0)
    perdida = -delta.clip(upper=0)

    media_ganancia = ganancia.rolling(periodo).mean()
    media_perdida = perdida.rolling(periodo).mean()

    rs = media_ganancia / media_perdida.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def _calcular_ema(cierre: pd.Series, periodo: int) -> float:
    return round(float(cierre.ewm(span=periodo, adjust=False).mean().iloc[-1]), 2)


def _calcular_atr(df: pd.DataFrame, periodo: int = 14) -> float:
    alto_bajo = df["high"] - df["low"]
    alto_cierre_prev = (df["high"] - df["close"].shift()).abs()
    bajo_cierre_prev = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([alto_bajo, alto_cierre_prev, bajo_cierre_prev], axis=1).max(axis=1)
    atr = tr.rolling(periodo).mean().iloc[-1]
    return round(float(atr), 2)


def _soporte_resistencia(df: pd.DataFrame, ventana: int = 40) -> tuple[float, float]:
    """
    Método simple: toma el mínimo y máximo de las últimas N velas como
    soporte y resistencia inmediatos. Suficiente para una primera versión;
    más adelante se puede mejorar con detección de pivots (swing highs/lows).
    """
    recorte = df.tail(ventana)
    return round(float(recorte["low"].min()), 2), round(float(recorte["high"].max()), 2)


async def calcular_indicadores() -> Indicadores:
    df = await _obtener_velas()

    rsi = _calcular_rsi(df["close"])
    ema20 = _calcular_ema(df["close"], 20)
    ema50 = _calcular_ema(df["close"], 50)
    atr = _calcular_atr(df)
    soporte, resistencia = _soporte_resistencia(df)

    if ema20 > ema50 * 1.001:
        tendencia = "alcista"
    elif ema20 < ema50 * 0.999:
        tendencia = "bajista"
    else:
        tendencia = "lateral"

    return Indicadores(
        rsi=rsi,
        ema_20=ema20,
        ema_50=ema50,
        tendencia=tendencia,
        soporte=soporte,
        resistencia=resistencia,
        volatilidad_atr=atr,
    )
