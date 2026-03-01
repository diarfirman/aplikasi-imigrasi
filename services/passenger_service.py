from elasticsearch import NotFoundError
from elasticsearch_client import get_es_client
from config import Config

NATIONALITY_FLAGS = {
    "ID": "🇮🇩", "MY": "🇲🇾", "SG": "🇸🇬", "AU": "🇦🇺",
    "US": "🇺🇸", "CN": "🇨🇳", "GB": "🇬🇧", "JP": "🇯🇵",
    "DE": "🇩🇪", "NL": "🇳🇱", "SA": "🇸🇦", "KR": "🇰🇷",
    "IN": "🇮🇳", "FR": "🇫🇷", "IT": "🇮🇹", "ES": "🇪🇸",
}


def get_passenger(passport_number: str) -> dict | None:
    """Ambil data penumpang berdasarkan nomor paspor."""
    es = get_es_client()
    try:
        response = es.get(index=Config.INDEX_PASSENGERS, id=passport_number.upper())
        return response["_source"]
    except NotFoundError:
        return None
    except Exception as e:
        raise RuntimeError(f"Gagal mengambil data penumpang: {e}")


def get_travel_history_sorted(passenger: dict) -> list:
    """Kembalikan riwayat perjalanan diurutkan dari yang terbaru."""
    history = passenger.get("travel_history", [])
    return sorted(history, key=lambda x: x.get("date", ""), reverse=True)


def get_nationality_flag(nationality_code: str) -> str:
    return NATIONALITY_FLAGS.get(nationality_code, "🌍")


def format_date_display(date_str: str) -> str:
    """Konversi 'YYYY-MM-DD' ke 'DD Bulan YYYY' dalam bahasa Indonesia."""
    if not date_str:
        return "-"
    MONTHS = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    try:
        parts = date_str.split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{day} {MONTHS[month]} {year}"
    except Exception:
        return date_str
