"""Pengecekan dependensi untuk health endpoint. Tiap check terisolasi dan tidak pernah raise."""
import json
import urllib.request

import redis
from django.conf import settings
from django.db import connection


def check_database() -> dict:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": type(exc).__name__}


def check_redis() -> dict:
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": type(exc).__name__}


def check_ollama() -> dict:
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310 - URL tetap dari konfigurasi
            models = json.load(resp).get("models", [])
        return {"status": "ok", "model_count": len(models)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": type(exc).__name__}


def run_all_checks() -> dict:
    return {
        "database": check_database(),
        "redis": check_redis(),
        "ollama": check_ollama(),
    }