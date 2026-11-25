# 📌 Pendientes y mejoras futuras

Proyecto en pausa. Estado al 25/11/2026: funcionando en local con Docker (API, worker, beat, Redis, Flower) y panel visual en http://localhost:8000.

## Mejoras acordadas (en este orden)

- [ ] **1. Guardar el historial en disco:** hoy `docker compose down` borra los precios porque Redis no tiene volumen. Agregar un volumen y `--appendonly yes` al servicio `redis`.
- [ ] **4. Calculadora minera:** ingresar toneladas de mineral y ley (%) y calcular el valor de la producción con el precio del día.
- [ ] **6. Pruebas automáticas (GitHub Actions):** tests con pytest y la insignia "passing" en el README.

## Otras ideas

- [ ] **2. Alertas** por Telegram o correo cuando un metal sube o baja más de X% (reutilizar la tarea `send_bulk_emails`).
- [ ] **3. Precios en moneda local** (soles) con el tipo de cambio.
- [ ] **5. Descargar el historial en Excel/CSV** desde el panel.
- [ ] **7. Publicarlo en internet** (Render o Railway) para tener un link público.
- [ ] **Práctica de SQL:** base de datos minera de práctica con datos inventados (camiones, turnos, toneladas, fallas) y 30 ejercicios de fácil a difícil con soluciones.

## Notas para retomar

- En Windows, usar `docker.exe` en vez de `docker` (si no, Windows pregunta con qué programa abrir un archivo llamado "docker").
- Comandos: `git pull origin main` → `docker.exe compose up --build` → abrir http://localhost:8000
- `kombu` está fijado en 5.4.2 a propósito (la versión 5.7 rompe el worker en python:3.12-slim).
