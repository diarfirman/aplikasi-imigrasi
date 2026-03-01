import re
import time
import logging

from opentelemetry.trace import Status, StatusCode

from elasticsearch_client import get_es_client
from config import Config
from telemetry import get_tracer, get_meter

logger = logging.getLogger(__name__)
_tracer = get_tracer()
_meter = get_meter()

# ── Metrics instruments ───────────────────────────────────────────────────────
_search_counter = _meter.create_counter(
    "imigrasi.search.requests",
    description="Total permintaan pencarian penumpang",
)
_search_latency = _meter.create_histogram(
    "imigrasi.search.duration_ms",
    description="Latensi pencarian penumpang dalam milidetik",
    unit="ms",
)

PASSPORT_PATTERNS = [
    r"^[A-Z]\d{7}$",          # Indonesia: A1234567
    r"^MY[A-Z]\d{6}$",        # Malaysia: MYA773421
    r"^[EK]\d{7}$",           # Singapura: E1234567
    r"^[NP][A-Z]\d{7}$",      # Australia: NA1234567
    r"^[A-Z]\d{8}$",          # USA: A12345678
    r"^G\d{8}$",              # China/Saudi: G12345678
    r"^M\d{8}$",              # Korea: M12345678
    r"^[A-Z]{2}\d{7}$",       # GB: AB1234567
    r"^[A-Z0-9]{6,12}$",      # Fallback generic
]


def looks_like_passport(query: str) -> bool:
    """Heuristic: apakah query terlihat seperti nomor paspor?"""
    q = query.upper().strip().replace(" ", "")
    if " " in query.strip():
        return False
    return any(re.match(p, q) for p in PASSPORT_PATTERNS)


def _build_filters(
    gender: str = None,
    date_of_birth: str = None,
    nationality: str = None,
) -> list:
    """
    Bangun daftar filter clause untuk bool/filter context.

    Filter context vs must context:
    ┌─────────────┬──────────────────────────────┬───────────────────────┐
    │             │ must (query context)          │ filter context        │
    ├─────────────┼──────────────────────────────┼───────────────────────┤
    │ Scoring     │ Ya - mempengaruhi _score      │ Tidak - hanya yes/no  │
    │ Caching     │ Tidak                         │ Ya - ES cache hasil   │
    │ Performa    │ Lebih lambat                  │ Lebih cepat           │
    │ Cocok untuk │ Full-text (nama)              │ Keyword/date/boolean  │
    └─────────────┴──────────────────────────────┴───────────────────────┘

    Gender, DOB, dan nationality adalah nilai diskrit (keyword/date),
    sehingga lebih tepat menggunakan filter context.
    """
    filters = []

    if gender and gender in ("M", "F"):
        filters.append({"term": {"gender": gender}})

    if date_of_birth and re.match(r"^\d{4}-\d{2}-\d{2}$", date_of_birth):
        filters.append({"term": {"date_of_birth": date_of_birth}})

    if nationality and len(nationality) == 2:
        filters.append({"term": {"nationality": nationality.upper()}})

    return filters


def search_passengers(
    query: str,
    search_type: str = "auto",
    gender: str = None,
    date_of_birth: str = None,
    nationality: str = None,
) -> list:
    """
    Cari penumpang di Elasticsearch dengan dukungan filter tambahan.

    search_type:
      "passport" -> exact term query pada passport_number
      "name"     -> fuzzy text search pada full_name
      "auto"     -> deteksi otomatis berdasarkan format query

    Filter opsional (filter context — cached, tidak mempengaruhi skor):
      gender        -> "M" atau "F"
      date_of_birth -> format "YYYY-MM-DD"
      nationality   -> kode ISO 2 huruf, misal "ID", "MY"
    """
    es = get_es_client()
    q = query.strip()

    # Tentukan tipe pencarian sebelum span dibuka agar bisa dijadikan atribut
    is_passport = search_type == "passport" or (
        search_type == "auto" and looks_like_passport(q)
    )
    detected_type = "passport" if is_passport else "name"

    # Mask nomor paspor di log (4 karakter terakhir disembunyikan)
    safe_query = (q[:-4] + "****") if detected_type == "passport" and len(q) > 4 else q

    active_filters = [
        f for f, v in [
            ("gender", gender),
            ("date_of_birth", date_of_birth),
            ("nationality", nationality),
        ]
        if v
    ]

    with _tracer.start_as_current_span("search_passengers") as span:
        span.set_attributes({
            "search.query_type": detected_type,
            "search.has_gender_filter": gender is not None,
            "search.has_dob_filter": date_of_birth is not None,
            "search.has_nationality_filter": nationality is not None,
            "search.filter_count": len(active_filters),
        })

        _search_counter.add(1, {"search.type": detected_type})
        t0 = time.monotonic()

        filters = _build_filters(gender, date_of_birth, nationality)

        if is_passport:
            # Passport sudah unik — filter tambahan tidak relevan
            body = {
                "query": {
                    "term": {"passport_number": q.upper()}
                },
                "size": 1,
            }
        else:
            # Nama: fuzzy matching di must (scoring) + filter opsional (filter context)
            name_query = {
                "should": [
                    {
                        "match": {
                            "full_name": {
                                "query": q,
                                "fuzziness": "AUTO",
                                "boost": 1.0,
                            }
                        }
                    },
                    {
                        "match_phrase_prefix": {
                            "full_name": {
                                "query": q,
                                "boost": 2.0,
                            }
                        }
                    },
                ],
                "minimum_should_match": 1,
            }

            if filters:
                body = {
                    "query": {
                        "bool": {
                            "must": [{"bool": name_query}],
                            "filter": filters,
                        }
                    },
                    "size": 20,
                }
            else:
                body = {
                    "query": {"bool": name_query},
                    "size": 20,
                }

        try:
            response = es.search(index=Config.INDEX_PASSENGERS, body=body)
            results = [hit["_source"] for hit in response["hits"]["hits"]]
            duration_ms = round((time.monotonic() - t0) * 1000, 1)

            span.set_attributes({
                "search.result_count": len(results),
                "search.duration_ms": duration_ms,
            })
            _search_latency.record(duration_ms, {"search.type": detected_type})

            logger.info(
                "search_passengers completed",
                extra={
                    "event": "search",
                    "query_sanitized": safe_query,
                    "query_type": detected_type,
                    "filters": active_filters,
                    "result_count": len(results),
                    "duration_ms": duration_ms,
                },
            )
            return results

        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(
                "search_passengers failed",
                exc_info=True,
                extra={
                    "query_sanitized": safe_query,
                    "query_type": detected_type,
                },
            )
            raise RuntimeError(f"Pencarian gagal: {e}")
