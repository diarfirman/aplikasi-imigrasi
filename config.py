import os
from dotenv import load_dotenv

load_dotenv()


def _parse_otlp_headers(raw: str) -> dict:
    """
    Parse OTLP header string dari format env var ke dict.

    Format: "Key=Value,Key2=Value2"
    Nilai bisa mengandung '=' (e.g. base64 ApiKey token),
    sehingga setiap entry di-split hanya pada '=' PERTAMA.

    Contoh:
        "Authorization=ApiKey abc=="
        -> {"Authorization": "ApiKey abc=="}
    """
    if not raw:
        return {}
    headers = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if "=" in entry:
            key, value = entry.split("=", 1)
            headers[key.strip()] = value.strip()
    return headers


class Config:
    # Elasticsearch
    ES_URL = os.environ.get("ES_URL", "https://localhost:9200")
    ES_API_KEY = os.environ.get("ES_API_KEY", "")
    ES_USERNAME = os.environ.get("ES_USERNAME", "elastic")
    ES_PASSWORD = os.environ.get("ES_PASSWORD", "")

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    # Elasticsearch Index Names
    INDEX_PASSENGERS = "imigrasi_passengers"
    INDEX_BLACKLIST = "imigrasi_blacklist"

    # OpenTelemetry
    OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "https://localhost:4318")
    OTEL_HEADERS = _parse_otlp_headers(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""))
    OTEL_SERVICE_NAME = "checkpoint-imigrasi"
    OTEL_SERVICE_VERSION = "1.0.0"
    OTEL_ENVIRONMENT = os.environ.get("OTEL_ENVIRONMENT", "production")
