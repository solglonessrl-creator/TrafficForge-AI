from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..core.config import settings
import httpx

router = APIRouter()

class EmailRequest(BaseModel):
    to_email: str
    subject: str
    content: str

@router.post("/send-welcome")
async def send_welcome_email(email: str, name: str):
    """
    Envía un email de bienvenida automático.
    """
    subject = "¡Bienvenido a la revolución de TrafficForge AI!"
    content = f"Hola {name},\n\nGracias por interesarte en automatizar tu negocio con IA. Pronto un asesor te contactará o puedes entrar aquí: https://tu-sitio.com/curso"
    
    # Simulación de envío con SendGrid o Mailchimp
    if settings.SENDGRID_API_KEY:
        print(f"Enviando email real a {email} vía SendGrid...")
        # Lógica de integración real aquí
    else:
        print(f"[Simulación] Email enviado a {email} con asunto: {subject}")
    
    return {"message": f"Email de bienvenida enviado a {email}"}

@router.post("/trigger-sequence")
async def trigger_follow_up(email: str, step: int):
    """
    Activa una secuencia de seguimiento basada en el paso actual.
    """
    sequences = {
        1: "Recordatorio: Tu descuento del 50% expira en 24h.",
        2: "Testimonio: Cómo Juan facturó $2,000 extra usando TrafficForge.",
        3: "¿Aún tienes dudas? Hablemos por WhatsApp."
    }
    
    msg = sequences.get(step, "Contenido de seguimiento por defecto")
    print(f"[Secuencia] Paso {step} enviado a {email}: {msg}")
    
    return {"message": f"Paso {step} de la secuencia activado para {email}"}
