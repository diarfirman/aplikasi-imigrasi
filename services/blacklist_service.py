import logging
from datetime import datetime

from elasticsearch import NotFoundError
from opentelemetry.trace import Status, StatusCode

from elasticsearch_client import get_es_client
from config import Config
from telemetry import get_tracer, get_meter

logger = logging.getLogger(__name__)
_tracer = get_tracer()
_meter = get_meter()

# ── Metrics instruments ───────────────────────────────────────────────────────
_blacklist_hit_counter = _meter.create_counter(
    "imigrasi.blacklist.hits",
    description="Total pengecekan blacklist yang menghasilkan hit",
)
_blacklist_add_counter = _meter.create_counter(
    "imigrasi.blacklist.additions",
    description="Total entri baru yang ditambahkan ke blacklist",
)

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def check_blacklist(
    passport_number: str = None,
    full_name: str = None,
    date_of_birth: str = None,
) -> dict | None:
    """
    Cek apakah seseorang masuk daftar cekal.

    Logika pencocokan berlapis:
    1. Hit passport_number (exact) -> HIGH confidence
    2. Hit full_name (exact) + date_of_birth (match) -> HIGH confidence
    3. Hit full_name saja (DOB kosong/berbeda) -> SOFT warning

    Returns:
        dict dengan tambahan field 'match_confidence': 'HIGH' | 'SOFT'
        None jika tidak masuk blacklist
    """
    if not passport_number and not full_name:
        return None

    with _tracer.start_as_current_span("check_blacklist") as span:
        span.set_attributes({
            "blacklist.has_passport": passport_number is not None,
            "blacklist.has_full_name": full_name is not None,
            "blacklist.has_dob": date_of_birth is not None,
        })

        result = _check_blacklist_impl(passport_number, full_name, date_of_birth)
        hit = result is not None

        if hit:
            confidence = result.get("match_confidence", "")
            severity = result.get("severity", "")
            span.set_attributes({
                "blacklist.hit": True,
                "blacklist.confidence": confidence,
                "blacklist.severity": severity,
            })
            _blacklist_hit_counter.add(1, {
                "confidence": confidence,
                "severity": severity,
            })

        logger.info(
            "blacklist_check",
            extra={
                "event": "blacklist_check",
                "hit": hit,
                "confidence": result.get("match_confidence", "") if hit else "",
                "severity": result.get("severity", "") if hit else "",
            },
        )
        return result


def _check_blacklist_impl(
    passport_number: str = None,
    full_name: str = None,
    date_of_birth: str = None,
) -> dict | None:
    """
    Implementasi pengecekan blacklist ke Elasticsearch.
    Dipanggil dari check_blacklist() yang sudah membungkus span OTel.
    """
    es = get_es_client()

    # ── Step 1: Cek nomor paspor (exact match, konfiden tinggi) ──────────────
    if passport_number:
        try:
            resp = es.search(
                index=Config.INDEX_BLACKLIST,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"is_active": True}},
                                {"term": {"passport_number": passport_number.upper()}},
                            ]
                        }
                    },
                    "sort": [{"severity": {"order": "desc"}}],
                    "size": 1,
                },
            )
            hits = resp["hits"]["hits"]
            if hits:
                record = hits[0]["_source"].copy()
                record["match_confidence"] = "HIGH"
                record["match_reason"] = "Nomor paspor cocok dengan daftar cekal"
                return record
        except Exception:
            pass

    # ── Step 2: Cek nama + DOB ────────────────────────────────────────────────
    if full_name:
        try:
            resp = es.search(
                index=Config.INDEX_BLACKLIST,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"is_active": True}},
                                {"term": {"full_name.keyword": full_name}},
                            ]
                        }
                    },
                    "sort": [{"severity": {"order": "desc"}}],
                    "size": 5,
                },
            )
            hits = resp["hits"]["hits"]
            if hits:
                for hit in hits:
                    record = hit["_source"]
                    bl_dob = record.get("date_of_birth")
                    if date_of_birth and bl_dob and date_of_birth == bl_dob:
                        # Nama + DOB cocok -> HIGH confidence
                        result = record.copy()
                        result["match_confidence"] = "HIGH"
                        result["match_reason"] = "Nama lengkap dan tanggal lahir cocok dengan daftar cekal"
                        return result

                # Nama cocok tapi DOB tidak cocok/tidak ada -> SOFT warning
                # Ambil entry dengan severity tertinggi
                best = max(hits, key=lambda h: SEVERITY_ORDER.get(h["_source"].get("severity", "LOW"), 0))
                result = best["_source"].copy()
                result["match_confidence"] = "SOFT"
                result["match_reason"] = "Nama serupa ditemukan di daftar cekal - harap verifikasi identitas"
                return result
        except Exception:
            pass

    return None


def add_to_blacklist(data: dict) -> bool:
    """Tambahkan entri baru ke daftar cekal."""
    with _tracer.start_as_current_span("add_to_blacklist") as span:
        severity = data.get("severity", "")
        reason_code = data.get("reason_code", "")
        has_passport = bool(data.get("passport_number"))
        added_by = data.get("added_by", "unknown")

        span.set_attributes({
            "blacklist.severity": severity,
            "blacklist.reason_code": reason_code,
            "blacklist.has_passport": has_passport,
            "blacklist.added_by": added_by,
        })

        es = get_es_client()
        data["created_at"] = datetime.utcnow().isoformat()
        data["is_active"] = True

        try:
            result = es.index(index=Config.INDEX_BLACKLIST, document=data, refresh="wait_for")
            success = result["result"] in ("created", "updated")

            _blacklist_add_counter.add(1, {
                "severity": severity,
                "reason_code": reason_code,
            })
            logger.info(
                "blacklist_entry_added",
                extra={
                    "event": "blacklist_add",
                    "severity": severity,
                    "reason_code": reason_code,
                    "has_passport": has_passport,
                    "added_by": added_by,
                    "es_result": result.get("result"),
                },
            )
            return success

        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(
                "blacklist_add_failed",
                exc_info=True,
                extra={
                    "severity": severity,
                    "reason_code": reason_code,
                    "added_by": added_by,
                },
            )
            raise RuntimeError(f"Gagal menambahkan ke blacklist: {e}")


def get_severity_label(severity: str) -> str:
    labels = {
        "LOW": "Rendah",
        "MEDIUM": "Sedang",
        "HIGH": "Tinggi",
        "CRITICAL": "Kritis",
    }
    return labels.get(severity, severity)


def get_reason_label(reason_code: str) -> str:
    labels = {
        "DRUG_TRAFFICKING": "Penyelundupan Narkoba",
        "DRUG_POSSESSION": "Kepemilikan Narkoba",
        "TERRORISM_SUPPORT": "Dukungan Terorisme",
        "TERRORISM_FINANCING": "Pendanaan Terorisme",
        "HUMAN_TRAFFICKING": "Perdagangan Manusia",
        "SMUGGLING": "Penyelundupan Barang",
        "FRAUD_IMMIGRATION": "Penipuan Imigrasi",
        "CHILD_EXPLOITATION": "Eksploitasi Anak",
        "DEPORTEE_PROHIBITED": "Deportan Terlarang",
        "VISA_OVERSTAY_REPEAT": "Overstay Berulang",
        "WANTED_FOREIGN": "DPO Asing",
        "MONEY_LAUNDERING": "Pencucian Uang",
        "OTHER": "Lainnya",
    }
    return labels.get(reason_code, reason_code)
