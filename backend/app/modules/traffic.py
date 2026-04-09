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


class ContentRequest(BaseModel):
    platform: str # "tiktok", "instagram", "blog"
    topic: str
    target_audience: str
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
    if settings.GEMINI_MODEL:
        return settings.GEMINI_MODEL
    preferred = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.0-pro", "gemini-pro"]
    available = _list_gemini_models(client)
    available_set = set(available)
    for m in preferred:
        if m in available_set:
            return m
    return available[0] if available else "gemini-2.0-flash"

@router.post("/generate-content")
async def generate_content(request: ContentRequest):
    """
    Genera contenido optimizado para una plataforma específica usando IA.
    Solo disponible para usuarios autenticados con límites según plan SaaS.
    """
    # Verificación de llaves configuradas
    if not client_openai and not client_groq and not client_gemini:
        raise HTTPException(status_code=503, detail="Servicio de IA no configurado. Por favor añade tus API Keys en el archivo .env")

    prompt = f"""
    Actúa como un experto en marketing digital y copywriter senior.
    Genera un contenido viral para {request.platform} sobre el tema: {request.topic}.
    Público objetivo: {request.target_audience}.
    
    El contenido debe incluir:
    1. Un gancho (Hook) irresistible.
    2. El cuerpo del mensaje con valor real.
    3. Una llamada a la acción (CTA) clara para vender servicios de redes sociales o cursos.
    4. Hashtags relevantes.
    
    Formato: Texto estructurado.
    """
    
    try:
        if request.provider == "groq":
            if not client_groq:
                raise HTTPException(status_code=400, detail="Groq no está configurado.")
            response = client_groq.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "system", "content": "Eres un experto en crecimiento orgánico y ventas."},
                          {"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800
            )
            content = response.choices[0].message.content
        elif request.provider == "gemini":
            if not client_gemini:
                raise HTTPException(status_code=400, detail="Gemini no está configurado.")
            model_name = _pick_gemini_model(client_gemini)
            response = client_gemini.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            content = _gemini_text(response)
        else:
            if not client_openai:
                raise HTTPException(status_code=400, detail="OpenAI no está configurado.")
            response = client_openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "Eres un experto en crecimiento orgánico y ventas."},
                          {"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800
            )
            content = response.choices[0].message.content
            
        return {"content": content, "provider": request.provider}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/seo-article-outline")
async def get_article_outline(topic: str):
    """
    Genera una estructura de artículo SEO optimizada.
    """
    prompt = f"Crea un esquema SEO detallado para un artículo de blog sobre: {topic}. Incluye H1, H2s, H3s y palabras clave secundarias."
    
    try:
        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
        return {"outline": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
