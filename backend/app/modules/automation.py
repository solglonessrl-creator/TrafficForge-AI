from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess
import os
from .auth import get_current_user

router = APIRouter()

class AutomationRequest(BaseModel):
    account_id: str
    action: str # "post", "comment", "like"
    target_url: str

@router.post("/run-automation")
async def run_automation(request: AutomationRequest, current_user: dict = Depends(get_current_user)):
    """
    Ejecuta el script de automatización para una cuenta específica.
    Solo para usuarios Pro o Enterprise.
    """
    if current_user["plan"] == "free":
        raise HTTPException(status_code=403, detail="La automatización avanzada solo está disponible en planes PRO.")

    script_path = os.path.join(os.getcwd(), "scripts", "browser_automation.py")
    
    print(f"User {current_user['email']} iniciando bot para cuenta: {request.account_id}")
    
    try:
        subprocess.Popen([
            "python", script_path, 
            "--account", request.account_id, 
            "--action", request.action,
            "--url", request.target_url
        ])
        return {"message": f"Automatización para {request.account_id} iniciada correctamente."}
    except Exception as e:
        return {"error": f"Error al iniciar automatización: {str(e)}"}

@router.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """
    Simulación de estado de los bots del usuario.
    """
    return {
        "user": current_user["email"],
        "active_bots": 1,
        "tasks_completed": 12,
        "platform_status": "All systems operational"
    }
