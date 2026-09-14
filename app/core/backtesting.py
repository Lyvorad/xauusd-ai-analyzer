"""
Módulo de backtesting / medidor de efectividad.

Corre periódicamente (ver scheduler/jobs.py) y revisa los reportes que
ya tienen suficiente tiempo desde que se generaron (1h o 4h) pero aún
no fueron evaluados. Compara el precio actual contra el precio que
había al momento del reporte para decidir si la dirección predicha
("compra"/"venta") acertó.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.market_data import obtener_precio_consenso
from app.db.models import Reporte

logger = logging.getLogger("backtesting")

# Umbral mínimo de movimiento para considerar que el precio realmente
# se movió en una dirección (evita marcar "acierto" por ruido de 0.01%)
UMBRAL_MOVIMIENTO_PORCENTAJE = 0.05


def _evaluar_direccion(direccion: str, precio_inicial: float, precio_final: float) -> str:
    cambio_pct = (precio_final - precio_inicial) / precio_inicial * 100

    if abs(cambio_pct) < UMBRAL_MOVIMIENTO_PORCENTAJE:
        movimiento = "neutral"
    elif cambio_pct > 0:
        movimiento = "compra"
    else:
        movimiento = "venta"

    if direccion == "neutral":
        # Si la IA dijo neutral, consideramos acierto si el precio no se movió mucho
        return "acierto" if movimiento == "neutral" else "fallo"

    return "acierto" if direccion == movimiento else "fallo"


async def evaluar_reportes_pendientes(db: Session):
    ahora = datetime.now(timezone.utc)
    consenso_actual = await obtener_precio_consenso()
    precio_actual = consenso_actual.precio

    # --- Ventana de 1 hora ---
    limite_1h = ahora - timedelta(hours=1)
    pendientes_1h = (
        db.query(Reporte)
        .filter(Reporte.resultado_1h == "pendiente")
        .filter(Reporte.creado_en <= limite_1h)
        .all()
    )
    for r in pendientes_1h:
        r.precio_1h_despues = precio_actual
        r.resultado_1h = _evaluar_direccion(r.direccion, r.precio, precio_actual)

    # --- Ventana de 4 horas ---
    limite_4h = ahora - timedelta(hours=4)
    pendientes_4h = (
        db.query(Reporte)
        .filter(Reporte.resultado_4h == "pendiente")
        .filter(Reporte.creado_en <= limite_4h)
        .all()
    )
    for r in pendientes_4h:
        r.precio_4h_despues = precio_actual
        r.resultado_4h = _evaluar_direccion(r.direccion, r.precio, precio_actual)

    db.commit()

    logger.info(
        "Backtesting: %s reportes evaluados en ventana 1h, %s en ventana 4h",
        len(pendientes_1h), len(pendientes_4h),
    )
