from fastapi import APIRouter
from pydantic import BaseModel
import subprocess
import os
import uuid
from ..core.storage import read_json, utc_now_iso, write_json

router = APIRouter()

class AutomationRequest(BaseModel):
    account_id: str
    action: str # "post", "comment", "like"
    target_url: str

@router.post("/run-automation")
async def run_automation(request: AutomationRequest):
    """
    Ejecuta el script de automatización para una cuenta específica.
    """
    script_path = os.path.join(os.getcwd(), "scripts", "browser_automation.py")
    
    try:
        task_id = uuid.uuid4().hex
        tasks = read_json("automation_tasks", default={})
        tasks_dict = tasks if isinstance(tasks, dict) else {}
        tasks_dict[task_id] = {
            "id": task_id,
            "name": f"Bot {request.account_id}",
            "status": "RUNNING",
            "activity": f"Acción={request.action} URL={request.target_url}",
            "created_at": utc_now_iso(),
        }
        write_json("automation_tasks", tasks_dict)

        subprocess.Popen([
            "python", script_path, 
            "--account", request.account_id, 
            "--action", request.action,
            "--url", request.target_url
        ])
        return {"message": f"Automatización para {request.account_id} iniciada correctamente.", "task_id": task_id}
    except Exception as e:
        return {"error": f"Error al iniciar automatización: {str(e)}"}

@router.get("/status")
async def get_status():
    """
    Estado de bots basado en tareas registradas.
    """
    tasks = read_json("automation_tasks", default={})
    tasks_dict = tasks if isinstance(tasks, dict) else {}
    active_bots = sum(1 for t in tasks_dict.values() if isinstance(t, dict) and t.get("status") == "RUNNING")
    return {
        "active_bots": active_bots,
        "tasks_total": len(tasks_dict),
        "platform_status": "operational"
    }
