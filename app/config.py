"""
Configuración central del proyecto.
Todo lo que sea una clave, URL o parámetro ajustable vive aquí,
así nunca hay una API key "hardcodeada" en medio del código.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- IA ---
    gemini_api_key: str = ""

    # --- Precio del oro (todas opcionales: el sistema usa las que existan) ---
    twelve_data_api_key: str = ""
    alpha_vantage_api_key: str = ""
    goldapi_api_key: str = ""
    finnhub_api_key: str = ""
    metals_api_key: str = ""

    # --- Noticias ---
    marketaux_api_key: str = ""
    newsapi_api_key: str = ""
    gnews_api_key: str = ""

    # --- Base de datos ---
    database_url: str = "sqlite:///./local.db"

    # --- Control de uso ---
    cooldown_consulta_manual: int = 120  # segundos

    # Secreto compartido para que el Cron Job de Render pueda disparar
    # el análisis automático sin que el endpoint quede público
    cron_secret: str = "cambia-esto-en-produccion"


# Instancia única que se importa en todo el proyecto (patrón singleton simple)
settings = Settings()
