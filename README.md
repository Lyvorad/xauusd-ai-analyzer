# Asistente Inteligente de Análisis para Oro (XAU/USD) — Backend

Backend que analiza el mercado de oro combinando precio (consenso de varias
fuentes), indicadores técnicos, y noticias, para generar un reporte con
dirección probable, niveles clave y justificación — usando Gemini como motor
de IA.

## 1. Correr en local

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Abre .env y pon tus API keys (ver sección "APIs necesarias" abajo)

# Correr el servidor
uvicorn app.main:app --reload
```

La API queda disponible en `http://localhost:8000`. Documentación interactiva
automática (Swagger) en `http://localhost:8000/docs`.

En local, el scheduler interno (APScheduler) se activa solo si
`HABILITAR_SCHEDULER_LOCAL=true` (o si no se define la variable) y corre el
análisis automático cada 30 min dentro del mismo proceso.

## 2. Endpoints principales

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/reporte/ultimo` | Último análisis generado |
| POST | `/reporte/ahora` | Dispara un análisis en el momento (con cooldown anti-abuso) |
| GET | `/reporte/historial?limite=50` | Histórico de reportes |
| GET | `/reporte/precision?ventana=24h` | % de aciertos (backtesting) |
| POST | `/interno/ejecutar-analisis` | Uso interno del Cron Job (requiere header `x-cron-secret`) |
| GET | `/salud` | Health check |

## 3. APIs necesarias (todas tienen free tier para empezar)

**Precio del oro** (usa las que consigas, el sistema ignora las que falten
y calcula el consenso con las que sí respondan):
- Twelve Data → https://twelvedata.com
- Alpha Vantage → https://www.alphavantage.co
- GoldAPI.io → https://www.goldapi.io
- Finnhub → https://finnhub.io

**Noticias**:
- Marketaux → https://www.marketaux.com
- NewsAPI → https://newsapi.org
- GNews → https://gnews.io

**IA**:
- Gemini → https://aistudio.google.com (ya la tienes)

> Nota: `TWELVE_DATA_API_KEY` es obligatoria específicamente para el módulo
> de indicadores técnicos (`indicators.py`), porque es la fuente que provee
> las velas históricas. Las demás son opcionales pero recomendadas para
> tener consenso real.

## 4. Desplegar en Render.com

1. Sube este proyecto a un repositorio de GitHub.
2. En Render, "New" → "Blueprint" → conecta el repo. Render leerá
   `render.yaml` y creará automáticamente: el Web Service, el Cron Job, y
   la base de datos Postgres.
3. En el dashboard de Render, entra a cada servicio y carga las variables
   marcadas con `sync: false` en `render.yaml` (las API keys y el
   `CRON_SECRET` — invéntate un secreto largo y ponlo IGUAL en ambos
   servicios).
4. Ajusta `API_URL` en el Cron Job al dominio real que Render te asigne al
   Web Service (te lo muestra en el dashboard, algo como
   `https://oro-xauusd-api.onrender.com`).

## 5. Próximos módulos (no incluidos todavía en este primer corte)

- `economic_calendar.py` — alerta 15 min antes de eventos de alto impacto.
- `alerts.py` — alertas personalizadas por usuario (RSI extremo, confianza alta).
- Autenticación de usuarios (si el sistema va a tener varios clientes).
