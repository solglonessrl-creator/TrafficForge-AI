from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "TrafficForge AI Publicidad 24/7"
    LANDING_PAGE_URL: str = "https://librodeautoayuda.netlify.app"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
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
