"""
Pipeline central. Esta es la función que TANTO el scheduler automático
COMO el endpoint de "consulta ahora" llaman. Así garantizamos que el
análisis automático y el manual sean siempre idénticos en calidad y
lógica — solo cambia el campo `origen` para poder diferenciarlos después
en el histórico.
"""

import asyncio
import logging

from sqlalchemy.orm import Session

from app.core.market_data import obtener_precio_consenso
from app.core.indicators import calcular_indicadores
from app.core.news import obtener_noticias_relevantes
from app.core.ai_engine import analizar
from app.db.models import Reporte

logger = logging.getLogger("pipeline")


async def generar_analisis(db: Session, origen: str = "manual") -> Reporte:
    # Precio, indicadores y noticias se piden EN PARALELO: no hay razón
    # para esperar a que termine uno antes de empezar el otro.
    precio, indicadores, noticias = await asyncio.gather(
        obtener_precio_consenso(),
        calcular_indicadores(),
        obtener_noticias_relevantes(),
    )

    resultado_ia = await analizar(precio, indicadores, noticias)

    reporte = Reporte(
        origen=origen,
        precio=precio.precio,
        fuentes_precio=",".join(precio.fuentes_usadas),
        rsi=indicadores.rsi,
        ema_20=indicadores.ema_20,
        ema_50=indicadores.ema_50,
        tendencia_tecnica=indicadores.tendencia,
        direccion=resultado_ia.direccion,
        confianza=resultado_ia.confianza,
        soporte=resultado_ia.soporte,
        resistencia=resultado_ia.resistencia,
        resumen=resultado_ia.resumen,
        riesgos=resultado_ia.riesgos,
        resultado_1h="pendiente",
        resultado_4h="pendiente",
    )

    db.add(reporte)
    db.commit()
    db.refresh(reporte)

    logger.info(
        "Reporte #%s generado (%s): %s a $%s con %s%% de confianza",
        reporte.id, origen, reporte.direccion, reporte.precio, reporte.confianza,
    )

    return reporte
