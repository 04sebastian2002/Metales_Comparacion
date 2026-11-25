"""
Las TAREAS: el trabajo pesado que NO queremos ejecutar dentro de la petición web.

Cada función decorada con @celery_app.task se convierte en una tarea que el
worker puede ejecutar en segundo plano. La API solo las "encola" y sigue
respondiendo al usuario al instante.
"""
import time
from pathlib import Path

from PIL import Image

from app import metals
from app.celery_app import celery_app


@celery_app.task(bind=True, name="tasks.resize_image")
def resize_image(self, input_path: str, width: int = 800, height: int = 600):
    """
    Redimensiona una imagen.

    'bind=True' nos da acceso a 'self' (la instancia de la tarea), que usamos
    para reportar progreso con self.update_state(). El time.sleep simula que
    esto es un proceso costoso.
    """
    self.update_state(state="PROGRESS", meta={"paso": "abriendo imagen", "percent": 10})
    time.sleep(1)  # simula trabajo pesado

    img = Image.open(input_path)

    self.update_state(state="PROGRESS", meta={"paso": "redimensionando", "percent": 50})
    time.sleep(1)
    img = img.resize((width, height))

    self.update_state(state="PROGRESS", meta={"paso": "guardando", "percent": 90})
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"resized_{Path(input_path).name}"
    img.save(output_path)
    time.sleep(0.5)

    return {"output_path": str(output_path), "size": [width, height]}


@celery_app.task(bind=True, name="tasks.send_bulk_emails")
def send_bulk_emails(self, recipients: list, subject: str, body: str):
    """
    Simula el envío de correos masivos, uno por uno, reportando el avance.

    En producción, aquí iría tu conexión SMTP real (smtplib) o un servicio
    como SendGrid/SES. El sleep simula la latencia de cada envío.
    """
    total = len(recipients)
    enviados = []

    for i, destinatario in enumerate(recipients, start=1):
        time.sleep(0.3)  # simula la latencia de un envío SMTP real
        enviados.append(destinatario)
        self.update_state(
            state="PROGRESS",
            meta={"enviados": i, "total": total, "percent": int(i / total * 100)},
        )

    return {"enviados": total, "asunto": subject, "destinatarios": enviados}


@celery_app.task(
    bind=True,
    name="tasks.update_metal_prices",
    autoretry_for=(OSError,),   # errores de red: reintenta solo
    retry_backoff=True,
    max_retries=3,
)
def update_metal_prices(self):
    """
    Consulta el precio actual del cobre, oro y plata y lo guarda en el historial.

    Se ejecuta solo cada cierto tiempo gracias a Celery Beat (ver celery_app.py),
    y también se puede lanzar a mano desde la API con POST /metals/update.
    """
    r = metals.get_redis()
    total = len(metals.METALES)
    lecturas = []
    errores = {}

    for i, symbol in enumerate(metals.METALES, start=1):
        try:
            price = metals.fetch_price(symbol)
        except Exception as exc:  # un metal que falla no detiene a los demás
            errores[symbol] = str(exc)
            continue
        reading = metals.build_reading(symbol, price)
        metals.save_reading(r, reading)
        lecturas.append(reading)
        self.update_state(
            state="PROGRESS",
            meta={"metal": reading["metal"], "percent": int(i / total * 100)},
        )

    if not lecturas:
        raise OSError(f"No se pudo obtener ningún precio: {errores}")

    return {"lecturas": lecturas, "errores": errores}
