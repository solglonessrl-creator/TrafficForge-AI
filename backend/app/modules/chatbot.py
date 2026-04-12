from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from groq import Groq
from ..core.config import has_real_secret, settings

router = APIRouter()

try:
    from google import genai as google_genai
except Exception:
    google_genai = None


class LeadMessage(BaseModel):
    lead_id: str
    message: str
    channel: str # "whatsapp", "dm_instagram", "email"
    provider: str = "openai" # "openai", "groq", "gemini"

client_openai = OpenAI(api_key=settings.OPENAI_API_KEY) if has_real_secret(settings.OPENAI_API_KEY) else None
client_groq = Groq(api_key=settings.GROQ_API_KEY) if has_real_secret(settings.GROQ_API_KEY) else None

client_gemini = (
    google_genai.Client(api_key=settings.GEMINI_API_KEY)
    if has_real_secret(settings.GEMINI_API_KEY) and google_genai
    else None
)


def _gemini_text(result) -> str:
    text = getattr(result, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    try:
        return str(result.candidates[0].content.parts[0].text).strip()
    except Exception:
        return str(result).strip()


def _list_gemini_models(client) -> list[str]:
    try:
        res = client.models.list()
    except Exception:
        return []
    names: list[str] = []
    try:
        for m in res:
            name = getattr(m, "name", None) or getattr(m, "model", None)
            if isinstance(name, str) and name:
                if name.startswith("models/"):
                    name = name.split("/", 1)[1]
                names.append(name)
    except Exception:
        return []
    return names


def _pick_gemini_model(client) -> str:
    forced = settings.GEMINI_MODEL or getattr(settings, "GEMINI_MODELO", None)
    if forced:
        return forced
    preferred = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-pro-latest"]
    available = _list_gemini_models(client)
    available_set = set(available)
    for m in preferred:
        if m in available_set:
            return m
    return available[0] if available else "gemini-2.0-flash"

# Script base de ventas
SALES_CONTEXT = """
Eres un asistente experto en ventas para TrafficForge AI.
Nuestros servicios principales son:
1. Automatización de redes sociales (TikTok/IG/FB) - $49/mes.
2. Desarrollo de landing pages con IA - $199 pago único.
3. Curso completo de Marketing con IA - $99.
"""

@router.post("/respond")
async def chat_with_lead(request: LeadMessage):
    """
    Responde a un lead. Solo para usuarios con suscripción activa.
    """
    if not client_openai and not client_groq and not client_gemini:
        raise HTTPException(status_code=503, detail="IA no configurada. Por favor añade tus API Keys.")

    try:
        if request.provider == "groq":
            if not client_groq:
                raise HTTPException(status_code=400, detail="Groq no está configurado.")
            response = client_groq.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "system", "content": SALES_CONTEXT}, {"role": "user", "content": request.message}],
                temperature=0.8
            )
            ai_response = response.choices[0].message.content
        elif request.provider == "gemini":
            if not client_gemini:
                raise HTTPException(status_code=400, detail="Gemini no está configurado.")
            model_name = _pick_gemini_model(client_gemini)
            response = client_gemini.models.generate_content(
                model=model_name,
                contents=f"{SALES_CONTEXT}\n\nLead dice: {request.message}",
            )
            ai_response = _gemini_text(response)
        else:
            if not client_openai:
                raise HTTPException(status_code=400, detail="OpenAI no está configurado.")
            response = client_openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": SALES_CONTEXT}, {"role": "user", "content": request.message}],
                temperature=0.8
            )
            ai_response = response.choices[0].message.content
            
        return {"response": ai_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
