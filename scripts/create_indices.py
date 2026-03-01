"""
Script untuk membuat Elasticsearch indices dan mappings untuk Aplikasi Checkpoint Imigrasi.

Usage:
    python scripts/create_indices.py           # Buat index baru (gagal jika sudah ada)
    python scripts/create_indices.py --force   # Hapus dan buat ulang index
"""

import sys
import argparse

sys.path.insert(0, ".")

from elasticsearch_client import get_es_client
from config import Config


PASSENGERS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "name_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                }
            }
        },
    },
    "mappings": {
        "properties": {
            "passport_number": {"type": "keyword"},
            "full_name": {
                "type": "text",
                "analyzer": "name_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "nationality": {"type": "keyword"},
            "nationality_name": {"type": "keyword"},
            "date_of_birth": {"type": "date", "format": "yyyy-MM-dd"},
            "gender": {"type": "keyword"},
            "place_of_birth": {"type": "keyword"},
            "passport_expiry": {"type": "date", "format": "yyyy-MM-dd"},
            "passport_issue_date": {"type": "date", "format": "yyyy-MM-dd"},
            "passport_issue_place": {"type": "keyword"},
            "occupation": {"type": "keyword"},
            "address": {"type": "text"},
            "photo_url": {"type": "keyword", "index": False},
            "travel_history": {
                "type": "nested",
                "properties": {
                    "date": {"type": "date", "format": "yyyy-MM-dd"},
                    "direction": {"type": "keyword"},
                    "port_of_entry": {"type": "keyword"},
                    "visa_type": {"type": "keyword"},
                    "visa_number": {"type": "keyword"},
                    "purpose": {"type": "keyword"},
                    "duration_days": {"type": "integer"},
                    "flight_number": {"type": "keyword"},
                    "country_from": {"type": "keyword"},
                    "country_to": {"type": "keyword"},
                    "officer_notes": {"type": "text"},
                },
            },
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        }
    },
}

BLACKLIST_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
    },
    "mappings": {
        "properties": {
            "passport_number": {"type": "keyword"},
            "full_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "nationality": {"type": "keyword"},
            "date_of_birth": {"type": "date", "format": "yyyy-MM-dd"},
            "severity": {"type": "keyword"},
            "reason": {"type": "text"},
            "reason_code": {"type": "keyword"},
            "issuing_authority": {"type": "keyword"},
            "blacklist_date": {"type": "date", "format": "yyyy-MM-dd"},
            "expiry_date": {"type": "date", "format": "yyyy-MM-dd"},
            "case_number": {"type": "keyword"},
            "referring_agency": {"type": "keyword"},
            "is_active": {"type": "boolean"},
            "notes": {"type": "text"},
            "created_at": {"type": "date"},
            "added_by": {"type": "keyword"},
        }
    },
}


def create_index(es, index_name, mapping, force=False):
    exists = es.indices.exists(index=index_name)

    if exists:
        if force:
            print(f"  [HAPUS] Index '{index_name}' sudah ada, menghapus...")
            es.indices.delete(index=index_name)
        else:
            print(f"  [SKIP]  Index '{index_name}' sudah ada. Gunakan --force untuk membuat ulang.")
            return False

    print(f"  [BUAT]  Membuat index '{index_name}'...")
    es.indices.create(index=index_name, body=mapping)
    print(f"  [OK]    Index '{index_name}' berhasil dibuat.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Buat Elasticsearch indices untuk Checkpoint Imigrasi")
    parser.add_argument("--force", action="store_true", help="Hapus dan buat ulang index yang sudah ada")
    args = parser.parse_args()

    print("\n=== Checkpoint Imigrasi - Index Creator ===\n")
    print(f"Menghubungi Elasticsearch: {Config.ES_URL}")

    try:
        es = get_es_client()
        info = es.info()
        print(f"Terhubung ke cluster: {info['cluster_name']} (v{info['version']['number']})\n")
    except Exception as e:
        print(f"[ERROR] Gagal terhubung ke Elasticsearch: {e}")
        sys.exit(1)

    print("--- Membuat Indices ---")
    create_index(es, Config.INDEX_PASSENGERS, PASSENGERS_MAPPING, force=args.force)
    create_index(es, Config.INDEX_BLACKLIST, BLACKLIST_MAPPING, force=args.force)

    print("\n=== Selesai ===")
    print(f"  Index penumpang : {Config.INDEX_PASSENGERS}")
    print(f"  Index blacklist : {Config.INDEX_BLACKLIST}")
    print("\nJalankan 'python scripts/load_dummy_data.py' untuk memuat data dummy.")


if __name__ == "__main__":
    main()
