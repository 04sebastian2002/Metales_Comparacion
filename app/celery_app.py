"""
Configuración central de Celery.

Aquí definimos la instancia de Celery que tanto la API (productor de tareas)
como el worker (consumidor de tareas) van a importar. Ambos apuntan al mismo
broker y al mismo backend, y así se "encuentran" a través de Redis.
"""
import os

from celery import Celery

# BROKER: la "cola de mensajes". Aquí la API deja las tareas pendientes.
#   -> usamos la base de datos 0 de Redis
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# BACKEND: donde el worker guarda los RESULTADOS de las tareas terminadas.
#   -> usamos la base de datos 1 de Redis (separada del broker por orden)
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "task_worker",
    broker=broker_url,
    backend=result_backend,
    # le decimos en qué módulo están las tareas para que las registre al arrancar
    include=["app.tasks"],
)

celery_app.conf.update(
    task_track_started=True,      # habilita el estado "STARTED" además de PENDING/SUCCESS
    task_serializer="json",       # cómo se serializan los argumentos de la tarea
    result_serializer="json",     # cómo se serializa el resultado
    accept_content=["json"],
    timezone="America/Lima",
    enable_utc=True,
    result_expires=3600,          # los resultados se borran de Redis tras 1 hora
)
