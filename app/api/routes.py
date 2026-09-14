import time

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.database import get_db
from app.db.models import Reporte
from app.core.pipeline import generar_analisis
from app.config import settings
from app.schemas import ReporteOut, PrecisionOut

router = APIRouter()

# Control simple de abuso para /reporte/ahora: guarda el último momento
# en que se pidió un análisis manual. Para producción con muchos usuarios
# esto debería vivir en Redis en vez de en memoria del proceso.
_ultima_consulta_manual: float = 0.0


@router.get("/salud")
def salud():
    return {"estado": "ok"}


@router.get("/reporte/ultimo", response_model=ReporteOut)
def reporte_ultimo(db: Session = Depends(get_db)):
    reporte = db.query(Reporte).order_by(desc(Reporte.creado_en)).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Todavía no hay ningún reporte generado")
    return reporte


@router.post("/reporte/ahora", response_model=ReporteOut)
async def reporte_ahora(db: Session = Depends(get_db)):
    global _ultima_consulta_manual

    ahora = time.time()
    segundos_desde_ultima = ahora - _ultima_consulta_manual
    if segundos_desde_ultima < settings.cooldown_consulta_manual:
        espera = round(settings.cooldown_consulta_manual - segundos_desde_ultima)
        raise HTTPException(
            status_code=429,
            detail=f"Espera {espera} segundos antes de pedir otro análisis manual",
        )

    _ultima_consulta_manual = ahora
    reporte = await generar_analisis(db, origen="manual")
    return reporte


@router.post("/interno/ejecutar-analisis", response_model=ReporteOut)
async def ejecutar_analisis_interno(
    x_cron_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """
    Endpoint pensado para que el Cron Job de Render (o el scheduler local)
    lo llame cada 30 min. Protegido con un header secreto compartido, NO
    para que lo use un usuario final directamente.
    """
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=403, detail="Secreto de cron inválido")

    reporte = await generar_analisis(db, origen="scheduler")
    return reporte


@router.get("/reporte/historial", response_model=list[ReporteOut])
def reporte_historial(limite: int = 50, db: Session = Depends(get_db)):
    limite = min(limite, 200)  # evita que alguien pida 1 millón de filas
    return (
        db.query(Reporte)
        .order_by(desc(Reporte.creado_en))
        .limit(limite)
        .all()
    )


@router.get("/reporte/precision", response_model=PrecisionOut)
def reporte_precision(ventana: str = "24h", db: Session = Depends(get_db)):
    """
    Calcula el % de aciertos usando la ventana de evaluación de 1h.
    (La ventana temporal de "últimas 24h" filtra por fecha de creación
    del reporte, no confundir con la ventana de evaluación 1h/4h).
    """
    from datetime import datetime, timedelta, timezone

    horas = {"24h": 24, "7d": 24 * 7}.get(ventana, 24)
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)

    evaluados = (
        db.query(Reporte)
        .filter(Reporte.creado_en >= desde)
        .filter(Reporte.resultado_1h.in_(["acierto", "fallo"]))
        .all()
    )

    total = len(evaluados)
    aciertos = len([r for r in evaluados if r.resultado_1h == "acierto"])
    porcentaje = round((aciertos / total * 100), 1) if total > 0 else 0.0

    return PrecisionOut(
        ventana=ventana,
        total_evaluados=total,
        aciertos=aciertos,
        porcentaje_precision=porcentaje,
    )
