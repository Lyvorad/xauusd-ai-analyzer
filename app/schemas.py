from datetime import datetime

from pydantic import BaseModel


class ReporteOut(BaseModel):
    id: int
    creado_en: datetime
    origen: str

    precio: float
    fuentes_precio: str
    rsi: float
    ema_20: float
    ema_50: float
    tendencia_tecnica: str

    direccion: str
    confianza: int
    soporte: float
    resistencia: float
    resumen: str
    riesgos: str

    resultado_1h: str | None = None
    resultado_4h: str | None = None

    model_config = {"from_attributes": True}  # permite construirlo desde el modelo de SQLAlchemy


class PrecisionOut(BaseModel):
    ventana: str  # "1h" | "4h"
    total_evaluados: int
    aciertos: int
    porcentaje_precision: float
