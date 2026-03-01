# Checkpoint Imigrasi

Aplikasi web pencarian dan pengelolaan daftar cekal (blacklist) penumpang lintas batas berbasis **Flask** dan **Elasticsearch**, dilengkapi instrumentasi **OpenTelemetry** untuk observabilitas penuh (traces, metrics, dan logs) ke Elastic Cloud.

---

## Fitur Utama

- **Pencarian Penumpang** — Cari berdasarkan nama (fuzzy) atau nomor paspor (exact), dengan filter gender, tanggal lahir, dan kewarganegaraan
- **Pengecekan Blacklist Otomatis** — Setiap pencarian otomatis dicocokkan dengan daftar cekal (confidence: HIGH / SOFT)
- **Manajemen Blacklist** — Form admin untuk menambahkan entri baru ke daftar cekal
- **Structured Logging (JSON)** — Setiap event penting (pencarian, pengecekan blacklist, penambahan cekal) dicatat sebagai JSON dengan `trace_id` dan `span_id`
- **OpenTelemetry** — Traces, metrics, dan logs dikirim ke Elastic Cloud via OTLP

---

## Tech Stack

| Layer | Teknologi |
|---|---|
| Backend | Python 3.x, Flask 3.1.1 |
| Database / Search | Elasticsearch 8.12.0 (Elastic Cloud) |
| Observabilitas | OpenTelemetry SDK 1.37.0, OTLP HTTP Exporter |
| Template | Jinja2, Bootstrap |
| Config | python-dotenv |

---

## Struktur Proyek

```
aplikasi_imigrasi/
├── app.py                    # Flask app factory
├── config.py                 # Konfigurasi (ES, Flask, OTel)
├── elasticsearch_client.py   # ES client singleton
├── logging_config.py         # JSON formatter + setup_logging()
├── telemetry.py              # OTel providers, exporters, instrumentors
├── requirements.txt
├── .env.example              # Template env vars
├── routes/
│   ├── search.py             # GET / dan POST /search
│   ├── passenger.py          # GET /passenger/<passport_number>
│   └── admin.py              # GET/POST /admin/blacklist
├── services/
│   ├── search_service.py     # Logika pencarian + OTel span
│   ├── blacklist_service.py  # Logika blacklist + OTel span
│   └── passenger_service.py  # Format data penumpang
├── scripts/
│   ├── create_indices.py     # Buat index Elasticsearch
│   └── load_dummy_data.py    # Load data dummy
├── static/
└── templates/
```

---

## Instalasi & Setup

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/diarfirman/aplikasi-imigrasi.git
cd aplikasi-imigrasi

pip install -r requirements.txt
```

### 2. Konfigurasi Environment

Salin `.env.example` menjadi `.env` dan isi nilainya:

```bash
cp .env.example .env
```

```env
# Elasticsearch (Elastic Cloud)
ES_URL=https://your-deployment.es.region.aws.found.io
ES_API_KEY=your_es_api_key_here

# Flask
SECRET_KEY=your-random-secret-key
FLASK_DEBUG=False

# OpenTelemetry → Elastic Cloud OTLP
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-deployment.ingest.region.aws.elastic-cloud.com:443
OTEL_EXPORTER_OTLP_HEADERS=Authorization=ApiKey your_otel_api_key_here
OTEL_ENVIRONMENT=production
```

### 3. Inisialisasi Index Elasticsearch

```bash
python scripts/create_indices.py
```

### 4. (Opsional) Load Data Dummy

```bash
python scripts/load_dummy_data.py
```

Akan membuat 200 data penumpang dan 10 data blacklist untuk testing.

### 5. Jalankan Aplikasi

```bash
python app.py
```

Aplikasi berjalan di: `http://localhost:5000`

---

## Endpoints

| Method | URL | Deskripsi |
|---|---|---|
| `GET` | `/` | Halaman utama / form pencarian |
| `POST` | `/search` | Pencarian penumpang |
| `GET` | `/passenger/<passport_number>` | Detail penumpang |
| `GET` | `/admin/blacklist` | Form tambah blacklist |
| `POST` | `/admin/blacklist` | Submit entri blacklist baru |

---

## Observabilitas (OpenTelemetry)

### Arsitektur Telemetry

```
Aplikasi Flask
    │
    ├── Traces  ──────────────────────────────┐
    │   • Auto: setiap HTTP request (Flask)   │
    │   • Auto: setiap query ES               │   OTLP HTTP
    │   • Custom: search_passengers           ├──────────────► Elastic Cloud
    │   • Custom: check_blacklist             │   /v1/traces
    │   • Custom: add_to_blacklist            │   /v1/metrics
    │                                         │   /v1/logs
    ├── Metrics ──────────────────────────────┤
    │   • imigrasi.search.requests            │
    │   • imigrasi.search.duration_ms         │
    │   • imigrasi.blacklist.hits             │
    │   • imigrasi.blacklist.additions        │
    │                                         │
    └── Logs ─────────────────────────────────┘
        • JSON structured ke stdout
        • Dikirim ke Elasticsearch via OTel LoggingHandler
```

### Contoh Log Record

Setiap log record selalu menyertakan `trace_id` dan `span_id` untuk korelasi dengan traces:

```json
{
  "@timestamp": "2026-03-01T04:03:33.192600+00:00",
  "level": "INFO",
  "logger": "services.search_service",
  "message": "search_passengers completed",
  "trace_id": "84df8ea710be47469e91bed07dd44c51",
  "span_id": "7b0c61c693346f88",
  "event": "search",
  "query_sanitized": "Ahmad",
  "query_type": "name",
  "result_count": 3,
  "duration_ms": 738.9
}
```

### Event Log yang Direkam

| Event | Logger | Field Tambahan |
|---|---|---|
| Pencarian penumpang | `services.search_service` | `query_type`, `result_count`, `duration_ms` |
| Pengecekan blacklist | `services.blacklist_service` | `hit`, `confidence`, `severity` |
| Penambahan blacklist | `services.blacklist_service` | `severity`, `reason_code`, `added_by` |
| HTTP request/response | `app` | `http.method`, `http.path`, `http.status_code` |
| Error | semua logger | `exception` (full traceback) |

### Melihat di Elastic Cloud

- **Traces** → APM → Services → `checkpoint-imigrasi`
- **Metrics** → Observability → Metrics Explorer → filter `service.name: checkpoint-imigrasi`
- **Logs** → Observability → Logs → filter `service.name: checkpoint-imigrasi`

---

## Konfigurasi OTel (service.name & version)

Service name dan version dikonfigurasi langsung di `config.py`:

```python
OTEL_SERVICE_NAME = "checkpoint-imigrasi"
OTEL_SERVICE_VERSION = "1.0.0"
```

---

## Lisensi

MIT
