"""
Scheduler para correr EN LOCAL (dentro del mismo proceso de FastAPI,
usando APScheduler). Cuando despliegues a Render, esto se reemplaza
por un Render Cron Job separado que golpea un endpoint interno
(ver sección "internal" en api/routes.py y el README).
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.database import SessionLocal
from app.core.pipeline import generar_analisis
from app.core.backtesting import evaluar_reportes_pendientes

logger = logging.getLogger("scheduler")

scheduler = AsyncIOScheduler()


async def _job_analisis_automatico():
    db = SessionLocal()
    try:
        await generar_analisis(db, origen="scheduler")
    except Exception:
        logger.exception("Falló el análisis automático programado")
    finally:
        db.close()


async def _job_backtesting():
    db = SessionLocal()
    try:
        await evaluar_reportes_pendientes(db)
    except Exception:
        logger.exception("Falló la evaluación de backtesting")
    finally:
        db.close()


def iniciar_scheduler():
    scheduler.add_job(_job_analisis_automatico, "interval", minutes=30, id="analisis_automatico")
    scheduler.add_job(_job_backtesting, "interval", hours=1, id="backtesting")
    scheduler.start()
    logger.info("Scheduler iniciado: análisis cada 30 min, backtesting cada hora")
