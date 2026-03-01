from elasticsearch import Elasticsearch
from config import Config

_client = None


def _normalize_url(url: str) -> str:
    """Tambahkan port 443 jika URL HTTPS tidak memiliki port eksplisit."""
    if url.startswith("https://") and ":" not in url.replace("https://", ""):
        return url + ":443"
    return url


def get_es_client() -> Elasticsearch:
    global _client
    if _client is None:
        host = _normalize_url(Config.ES_URL)
        if Config.ES_API_KEY:
            _client = Elasticsearch(
                host,
                api_key=Config.ES_API_KEY,
                verify_certs=True,
                request_timeout=30,
            )
        else:
            _client = Elasticsearch(
                host,
                basic_auth=(Config.ES_USERNAME, Config.ES_PASSWORD),
                verify_certs=True,
                request_timeout=30,
            )
    return _client
