from pydantic_settings import BaseSettings
from typing import Optional


def _is_placeholder(value: Optional[str]) -> bool:
    if not value:
        return True
    v = value.strip().lower()
    placeholders = [
        "tu-openai-key",
        "sk-tu-",
        "gsk_tu-",
        "gsk-tu-",
        "tu-groq-key",
        "tu-gemini-key",
        "sb_publishable_",
        "sb_secret_",
        "tu-anon-key",
        "tu-secret",
        "whsec_tu-",
    ]
    return any(p in v for p in placeholders)


def has_real_secret(value: Optional[str]) -> bool:
    return not _is_placeholder(value)

class Settings(BaseSettings):
    PROJECT_NAME: str = "TrafficForge AI Publicidad 24/7"
    LANDING_PAGE_URL: str = "https://librodeautoayuda.netlify.app"
    PUBLIC_BASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None
    GEMINI_MODELO: Optional[str] = None
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None
    
    # Configuración de automatización
    HEADLESS_BROWSER: bool = True
    HUMAN_DELAY_MIN: float = 1.0
    HUMAN_DELAY_MAX: float = 3.5
    
    class Config:
        env_file = ".env"

settings = Settings()
