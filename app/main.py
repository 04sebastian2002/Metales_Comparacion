"""
La API web (FastAPI).

Su única responsabilidad es RECIBIR peticiones y ENCOLAR tareas. Nunca ejecuta
el trabajo pesado: lo delega al worker y devuelve un task_id al instante para
que el cliente pueda consultar el progreso después.
"""
from pathlib import Path
from typing import List

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import metals
from app.celery_app import celery_app
from app.tasks import resize_image, send_bulk_emails, update_metal_prices

app = FastAPI(title="Sistema de Gestión de Tareas Distribuidas")


# --- Modelos de entrada (validación automática con Pydantic) ---
class ResizeRequest(BaseModel):
    input_path: str
    width: int = 800
    height: int = 600


class EmailRequest(BaseModel):
    recipients: List[str]
    subject: str
    body: str


# --- Endpoints que ENCOLAN trabajo ---
@app.post("/tasks/resize")
def submit_resize(req: ResizeRequest):
    # .delay() envía la tarea al broker y regresa de inmediato (no espera)
    task = resize_image.delay(req.input_path, req.width, req.height)
    return {"task_id": task.id, "status": "encolada"}


@app.post("/tasks/emails")
def submit_emails(req: EmailRequest):
    task = send_bulk_emails.delay(req.recipients, req.subject, req.body)
    return {"task_id": task.id, "status": "encolada"}


# --- Endpoint que CONSULTA el estado/resultado ---
@app.get("/tasks/{task_id}")
def get_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "state": result.state}

    if result.state == "PROGRESS":
        response["progress"] = result.info          # el dict que pusimos en update_state
    elif result.state == "SUCCESS":
        response["result"] = result.result           # lo que retornó la tarea
    elif result.state == "FAILURE":
        response["error"] = str(result.info)         # la excepción, si falló

    return response


# --- Monitor de precios de metales ---
@app.post("/metals/update")
def submit_metals_update():
    """Encola una actualización inmediata de precios (además de la automática)."""
    task = update_metal_prices.delay()
    return {"task_id": task.id, "status": "encolada"}


@app.get("/metals/prices")
def get_metal_prices():
    """Comparación actual: último precio, variaciones y ratio oro/plata."""
    comparacion = metals.build_comparison(metals.get_redis())
    if not comparacion["metales"]:
        raise HTTPException(
            status_code=404,
            detail="Aún no hay precios guardados. Llama a POST /metals/update o espera a la próxima actualización.",
        )
    return comparacion


@app.get("/metals/history/{symbol}")
def get_metal_history(symbol: str, limit: int = Query(50, ge=1, le=500)):
    """Historial de un metal: HG (cobre), XAU (oro) o XAG (plata)."""
    symbol = symbol.upper()
    if symbol not in metals.METALES:
        raise HTTPException(status_code=404, detail=f"Usa uno de: {', '.join(metals.METALES)}")
    return {
        "simbolo": symbol,
        "metal": metals.METALES[symbol]["nombre"],
        "historial": metals.get_history(metals.get_redis(), symbol, limit),
    }


STATIC_DIR = Path(__file__).parent / "static"
DASHBOARD = STATIC_DIR / "dashboard.html"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Panel visual (dashboard) ---
@app.get("/", include_in_schema=False)
def dashboard():
    """Panel web con los precios de los metales: http://localhost:8000"""
    return FileResponse(DASHBOARD)


@app.get("/health")
def health():
    return {"servicio": "task-worker", "estado": "ok"}
