FROM python:3.12-slim

WORKDIR /code

# dependencias del sistema (gcc por si alguna librería lo necesita al compilar)
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
