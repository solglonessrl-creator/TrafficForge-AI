from typing import Optional
from .config import settings

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = object

def get_supabase() -> Optional[Client]:
    if create_client is None:
        return None
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        print("⚠️ Advertencia: SUPABASE_URL o SUPABASE_KEY no configurados.")
        return None
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Singleton client (opcional, mejor en una clase)
supabase: Optional[Client] = get_supabase()
