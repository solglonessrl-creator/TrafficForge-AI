from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import stripe
from ..core.config import settings

router = APIRouter()

stripe.api_key = settings.STRIPE_API_KEY

class LeadCapture(BaseModel):
    name: str
    email: str
    whatsapp: str
    source: str # "facebook", "tiktok", "instagram", "seo"

class CheckoutRequest(BaseModel):
    email: str
    product_id: str # "social_bot", "landing_page", "marketing_course"

@router.post("/capture")
async def capture_lead(lead: LeadCapture):
    """
    Captura un nuevo lead en la base de datos de Supabase.
    """
    try:
        # data = supabase.table("leads").insert({
        #     "name": lead.name,
        #     "email": lead.email,
        #     "whatsapp": lead.whatsapp,
        #     "source": lead.source,
        #     "status": "new"
        # }).execute()
        
        # Simulamos éxito por ahora
        print(f"Lead capturado: {lead.email} desde {lead.source}")
        
        # URL de redirección a WhatsApp para el cierre de venta
        wa_message = f"Hola, vengo de TrafficForge AI y quiero más información sobre vuestros servicios."
        wa_link = f"https://wa.me/34600000000?text={wa_message.replace(' ', '%20')}"
        
        return {"message": "Lead capturado correctamente", "whatsapp_link": wa_link}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutRequest):
    """
    Crea una sesión de pago en Stripe para automatizar la venta.
    """
    products = {
        "social_bot": {"name": "Bot de Redes Sociales (Mensual)", "amount": 4900}, # en céntimos
        "landing_page": {"name": "Landing Page con IA", "amount": 19900},
        "marketing_course": {"name": "Curso Marketing IA", "amount": 9900}
    }
    
    product = products.get(request.product_id)
    if not product:
        raise HTTPException(status_code=400, detail="Producto no válido")
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': product['name']},
                    'unit_amount': product['amount'],
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://tu-sitio.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://tu-sitio.com/cancel',
            customer_email=request.email,
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Recibe notificaciones de Stripe sobre pagos completados.
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print(f"Pago completado para: {session['customer_email']}")
        # Aquí podrías activar automáticamente el servicio para el cliente
    
    return {"status": "success"}

@router.get("/funnel-stats")
# ... (código existente)
async def get_stats():
    """
    Devuelve estadísticas básicas del embudo.
    """
    # En un caso real, haríamos queries a Supabase para contar leads por fuente
    stats = {
        "total_leads": 125,
        "conversions_whatsapp": 45,
        "sales_closed": 12,
        "sources": {
            "tiktok": 60,
            "instagram": 40,
            "seo": 25
        }
    }
    return stats
