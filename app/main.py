import logging
import os

from fastapi import FastAPI

from app.db.database import Base, engine
from app.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("main")

# Crea las tablas si no existen (para algo más serio en producción se usaría
# Alembic para migraciones versionadas, pero para arrancar esto es suficiente)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Asistente Inteligente de Análisis para Oro (XAU/USD)",
    description="Backend de análisis automático de mercado combinando precio, indicadores técnicos y noticias, procesado por IA.",
    version="0.1.0",
)

app.include_router(router)


@app.on_event("startup")
async def startup():
    # El scheduler en el mismo proceso SOLO se activa en local.
    # En Render, el análisis automático lo dispara el Cron Job externo,
    # así que ahí dejamos esto apagado con la variable de entorno.
    if os.getenv("HABILITAR_SCHEDULER_LOCAL", "true").lower() == "true":
        from app.scheduler.jobs import iniciar_scheduler
        iniciar_scheduler()
    else:
        logger.info("Scheduler local desactivado (se usará Cron Job externo de Render)")
