from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, Text

from app.db.database import Base


class Reporte(Base):
    """
    Cada fila es un análisis completo generado por el sistema, ya sea
    automático (scheduler) o pedido manualmente por el usuario.
    """
    __tablename__ = "reportes"

    id = Column(Integer, primary_key=True, index=True)
    creado_en = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    origen = Column(String, default="manual")  # "scheduler" | "manual"

    # Datos de mercado en el momento del análisis
    precio = Column(Float)
    fuentes_precio = Column(String)  # ej. "twelve_data,goldapi"
    rsi = Column(Float)
    ema_20 = Column(Float)
    ema_50 = Column(Float)
    tendencia_tecnica = Column(String)

    # Resultado de la IA
    direccion = Column(String)      # "compra" | "venta" | "neutral"
    confianza = Column(Integer)     # 0-100
    soporte = Column(Float)
    resistencia = Column(Float)
    resumen = Column(Text)
    riesgos = Column(Text)

    # --- Campos para el módulo de backtesting (se llenan después) ---
    precio_1h_despues = Column(Float, nullable=True)
    precio_4h_despues = Column(Float, nullable=True)
    resultado_1h = Column(String, nullable=True)  # "acierto" | "fallo" | "pendiente"
    resultado_4h = Column(String, nullable=True)
