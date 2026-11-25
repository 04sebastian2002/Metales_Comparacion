"""
Monitor de precios de metales (cobre, oro y plata).

Consulta los precios spot en la API pública gratuita https://gold-api.com
(no requiere API key) y guarda un historial en Redis para poder comparar
cómo cambian los precios en el tiempo.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

import redis

PRICE_API_URL = os.getenv("METALS_API_URL", "https://api.gold-api.com/price/{symbol}")

# Usamos la base de datos 2 de Redis solo para el historial de precios
# (la 0 es el broker y la 1 los resultados de Celery).
REDIS_URL = os.getenv("METALS_REDIS_URL", "redis://localhost:6379/2")

# Máximo de lecturas que guardamos por metal (las más antiguas se descartan)
HISTORY_LIMIT = int(os.getenv("METALS_HISTORY_LIMIT", "500"))

LIBRAS_POR_TONELADA = 2204.62

METALES = {
    "HG": {"nombre": "Cobre", "unidad": "USD/lb"},
    "XAU": {"nombre": "Oro", "unidad": "USD/oz troy"},
    "XAG": {"nombre": "Plata", "unidad": "USD/oz troy"},
}


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _history_key(symbol: str) -> str:
    return f"metales:historial:{symbol}"


def fetch_price(symbol: str, timeout: float = 10.0) -> float:
    """Descarga el precio actual de un metal desde la API."""
    url = PRICE_API_URL.format(symbol=symbol)
    req = urllib.request.Request(url, headers={"User-Agent": "task-worker-system"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return float(data["price"])


def build_reading(symbol: str, price: float) -> dict:
    """Arma una lectura con el precio y sus conversiones útiles."""
    reading = {
        "simbolo": symbol,
        "metal": METALES[symbol]["nombre"],
        "precio": round(price, 4),
        "unidad": METALES[symbol]["unidad"],
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if symbol == "HG":
        # En minería el cobre se negocia normalmente en USD por tonelada métrica
        reading["precio_tonelada"] = round(price * LIBRAS_POR_TONELADA, 2)
    return reading


def save_reading(r: redis.Redis, reading: dict) -> None:
    key = _history_key(reading["simbolo"])
    r.lpush(key, json.dumps(reading))      # la más reciente queda primero
    r.ltrim(key, 0, HISTORY_LIMIT - 1)


def get_history(r: redis.Redis, symbol: str, limit: int = 50) -> list:
    raw = r.lrange(_history_key(symbol), 0, max(limit, 1) - 1)
    return [json.loads(item) for item in raw]


def variation(current: float, previous: float) -> float:
    """Variación porcentual entre dos precios."""
    if not previous:
        return 0.0
    return round((current - previous) / previous * 100, 2)


def build_comparison(r: redis.Redis) -> dict:
    """
    Compara los metales usando la última lectura de cada uno:
    - variación contra la lectura anterior y contra la primera guardada
    - ratio oro/plata (cuántas onzas de plata compra una onza de oro)
    """
    metales = {}
    for symbol in METALES:
        historial = get_history(r, symbol, HISTORY_LIMIT)
        if not historial:
            continue
        actual = historial[0]
        anterior = historial[1] if len(historial) > 1 else actual
        primera = historial[-1]
        metales[symbol] = {
            **actual,
            "variacion_vs_anterior_pct": variation(actual["precio"], anterior["precio"]),
            "variacion_vs_primera_pct": variation(actual["precio"], primera["precio"]),
            "lecturas": len(historial),
        }

    comparacion = {"metales": metales}
    if "XAU" in metales and "XAG" in metales and metales["XAG"]["precio"]:
        comparacion["ratio_oro_plata"] = round(
            metales["XAU"]["precio"] / metales["XAG"]["precio"], 2
        )
    if metales:
        comparacion["mayor_alza"] = max(
            metales.values(), key=lambda m: m["variacion_vs_anterior_pct"]
        )["metal"]
    return comparacion
