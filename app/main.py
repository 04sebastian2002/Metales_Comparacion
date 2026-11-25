"""
La API web (FastAPI).

Su única responsabilidad es RECIBIR peticiones y ENCOLAR tareas. Nunca ejecuta
el trabajo pesado: lo delega al worker y devuelve un task_id al instante para
que el cliente pueda consultar el progreso después.
"""
from typing import List

from celery.result import AsyncResult
from fastapi import FastAPI
from pydantic import BaseModel

from app.celery_app import celery_app
from app.tasks import resize_image, send_bulk_emails

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


@app.get("/")
def health():
    return {"servicio": "task-worker", "estado": "ok"}
