"""
Script untuk mengisi Elasticsearch dengan data dummy penumpang dan blacklist.

Usage:
    python scripts/load_dummy_data.py                    # Load default 200 penumpang
    python scripts/load_dummy_data.py --fresh            # Hapus data lama, load ulang
    python scripts/load_dummy_data.py --add 50           # Tambah 50 penumpang baru
    python scripts/load_dummy_data.py --dry-run          # Preview ke stdout saja
    python scripts/load_dummy_data.py --dry-run --output data.json  # Simpan ke file
"""

import sys
import json
import random
import argparse
from datetime import datetime, date, timedelta

sys.path.insert(0, ".")

from faker import Faker
from elasticsearch.helpers import bulk
from elasticsearch_client import get_es_client
from config import Config

# ─── Faker instances per locale ─────────────────────────────────────────────
fake_id = Faker("id_ID")
fake_ms = Faker("en_US")   # ms_MY tidak tersedia, pakai en_US dengan nama kustom
fake_en = Faker("en_US")
fake_zh = Faker("zh_CN")
fake_au = Faker("en_AU")
fake_gb = Faker("en_GB")
fake_jp = Faker("ja_JP")
fake_de = Faker("de_DE")
fake_ko = Faker("ko_KR")
fake_nl = Faker("nl_NL")
fake_sa = Faker("ar_SA")

# Malaysian names (hardcoded pool karena ms_MY tidak tersedia di Faker)
MALAY_MALE_NAMES = [
    "Ahmad bin Abdullah", "Mohd Hafiz bin Razali", "Muhammad Faizal bin Zulkifli",
    "Azri bin Hassan", "Khairul bin Othman", "Fadzli bin Ramli", "Nasrul bin Ismail",
    "Zulhelmi bin Baharudin", "Shafiq bin Talib", "Ridhwan bin Azman",
]
MALAY_FEMALE_NAMES = [
    "Nurul Ain binti Hassan", "Siti Norziana binti Yusof", "Farah Nadia binti Ahmad",
    "Norhasliza binti Che Mat", "Amirah binti Sulaiman", "Haslinda binti Ibrahim",
    "Roszaini binti Mohd Noor", "Balkish binti Zainudin",
]

Faker.seed(42)
random.seed(42)

# ─── Constants ───────────────────────────────────────────────────────────────
PORTS_OF_ENTRY = [
    "Bandar Udara Internasional Soekarno-Hatta (CGK)",
    "Bandar Udara Internasional Ngurah Rai - Bali (DPS)",
    "Bandar Udara Internasional Juanda - Surabaya (SUB)",
    "Bandar Udara Internasional Kualanamu - Medan (KNO)",
    "Bandar Udara Internasional Sultan Hasanuddin - Makassar (UPG)",
    "Bandar Udara Internasional Lombok (LOP)",
    "Pelabuhan Batam Centre",
    "Pelabuhan Tanjung Priok - Jakarta",
    "PLBN Entikong - Kalimantan Barat",
    "PLBN Motaain - Nusa Tenggara Timur",
]

VISA_TYPES = {
    "ID": ["Paspor WNI", "Paspor WNI"],
    "MY": ["Visa Kunjungan 30 Hari", "Visa Kunjungan Wisata"],
    "SG": ["Visa Kunjungan 30 Hari", "Visa Kunjungan Bisnis"],
    "AU": ["Visa Kunjungan B211A", "Visa Kunjungan Wisata"],
    "US": ["Visa Kunjungan B211A", "Visa Kunjungan Bisnis"],
    "CN": ["Visa Kunjungan 30 Hari", "Visa on Arrival"],
    "GB": ["Visa Kunjungan B211A", "Visa Kunjungan Wisata"],
    "JP": ["Visa Kunjungan 30 Hari", "Visa Kunjungan Wisata"],
    "DE": ["Visa Kunjungan B211A", "Visa Kunjungan Wisata"],
    "NL": ["Visa Kunjungan B211A", "Visa Kunjungan Wisata"],
    "SA": ["Visa Kunjungan 30 Hari", "Visa Ibadah Umroh"],
    "KR": ["Visa Kunjungan 30 Hari", "Visa Kunjungan Wisata"],
    "IN": ["Visa on Arrival", "Visa Kunjungan 30 Hari"],
    "default": ["Visa Kunjungan 30 Hari", "Visa on Arrival"],
}

FLIGHT_PREFIXES = {
    "ID": ["GA", "JT", "QG", "ID", "IW"],
    "MY": ["MH", "AK", "FY"],
    "SG": ["SQ", "TR", "MI"],
    "AU": ["QF", "VA", "JQ"],
    "US": ["UA", "AA", "DL", "US"],
    "CN": ["CA", "MU", "CZ"],
    "GB": ["BA", "VS", "EZ"],
    "JP": ["NH", "JL", "MM"],
    "DE": ["LH", "EW"],
    "NL": ["KL"],
    "SA": ["SV", "F3"],
    "KR": ["KE", "OZ"],
    "default": ["EK", "TK", "QR", "SU"],
}

PURPOSES_ARRIVAL = [
    "Kembali ke Indonesia",
    "Wisata",
    "Perjalanan Bisnis",
    "Kunjungan Keluarga",
    "Pendidikan",
    "Konferensi Internasional",
    "Investasi",
    "Transit",
]

PURPOSES_DEPARTURE = [
    "Perjalanan Bisnis",
    "Wisata",
    "Kunjungan Keluarga",
    "Pendidikan",
    "Haji/Umroh",
    "Tugas Pemerintah",
    "Bekerja di Luar Negeri",
    "Konferensi",
]

OCCUPATIONS = [
    "Pengusaha", "PNS", "Dokter", "Insinyur", "Guru", "Perawat",
    "Mahasiswa", "Pelajar", "Karyawan Swasta", "Pedagang", "Petani",
    "Nelayan", "Wiraswasta", "Diplomat", "TNI/Polri", "Pensiunan",
    "Ibu Rumah Tangga", "Artis", "Atlet", "Jurnalis", "Pengacara",
    "Arsitek", "Desainer", "Fotografer", "Programmer", "Akuntan",
]

NATIONALITIES = [
    ("ID", "Indonesia", 80),
    ("MY", "Malaysia", 30),
    ("SG", "Singapura", 20),
    ("AU", "Australia", 15),
    ("US", "Amerika Serikat", 12),
    ("CN", "Tiongkok", 12),
    ("GB", "Inggris", 8),
    ("JP", "Jepang", 8),
    ("DE", "Jerman", 5),
    ("NL", "Belanda", 5),
    ("SA", "Arab Saudi", 5),
    ("KR", "Korea Selatan", 5),
    ("IN", "India", 5),
]

# Passport number generators per country
def gen_passport(nat_code: str) -> str:
    r = random.randint
    c = random.choice
    alpha = "ABCDEFGHJKLMNPRSTUVWXYZ"
    digits = "0123456789"

    if nat_code == "ID":
        return f"{c('ABCDEFG')}{r(1000000, 9999999)}"
    elif nat_code == "MY":
        prefix = c(["A", "H", "K", "M", "P", "R", "T"])
        return f"MY{prefix}{''.join(random.choices(digits, k=6))}"
    elif nat_code == "SG":
        return f"{''.join(random.choices('EKLMST', k=1))}{''.join(random.choices(digits, k=7))}"
    elif nat_code == "AU":
        return f"{''.join(random.choices('NP', k=1))}{''.join(random.choices(alpha[:10], k=1))}{''.join(random.choices(digits, k=7))}"
    elif nat_code == "US":
        return f"{''.join(random.choices(alpha, k=1))}{''.join(random.choices(digits, k=8))}"
    elif nat_code == "CN":
        return f"G{''.join(random.choices(digits, k=8))}"
    elif nat_code == "GB":
        return f"{''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=2))}{''.join(random.choices(digits, k=7))}"
    elif nat_code == "JP":
        return f"{''.join(random.choices('ABCEFHJLMPTW', k=2))}{''.join(random.choices(digits, k=7))}"
    elif nat_code == "DE":
        return f"{''.join(random.choices('CDEFGHJKLMNPRSTUVWXYZ', k=1))}{''.join(random.choices(alpha, k=1))}{''.join(random.choices(digits, k=7))}"
    elif nat_code == "NL":
        return f"{''.join(random.choices('BCDEFGHJKLMNPRSTUVWXYZ', k=2))}{''.join(random.choices(digits, k=7))}"
    elif nat_code == "SA":
        return f"G{''.join(random.choices(digits, k=8))}"
    elif nat_code == "KR":
        return f"M{''.join(random.choices(digits, k=8))}"
    elif nat_code == "IN":
        return f"{''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=1))}{''.join(random.choices(digits, k=7))}"
    else:
        return f"{nat_code}{''.join(random.choices(digits, k=7))}"


def gen_flight_number(nat_code: str) -> str:
    prefixes = FLIGHT_PREFIXES.get(nat_code, FLIGHT_PREFIXES["default"])
    prefix = random.choice(prefixes)
    number = random.randint(100, 999)
    return f"{prefix}-{number}"


def gen_travel_history(nat_code: str, n: int = None) -> list:
    if n is None:
        n = random.randint(1, 5)

    history = []
    today = date.today()

    # Generate pairs of arrival/departure going backwards in time
    current_date = today - timedelta(days=random.randint(1, 30))

    for _ in range(n):
        # Arrival
        port = random.choice(PORTS_OF_ENTRY)
        visa_options = VISA_TYPES.get(nat_code, VISA_TYPES["default"])
        visa = random.choice(visa_options)
        flight = gen_flight_number(nat_code)

        if nat_code == "ID":
            country_from = random.choice(["SG", "MY", "AU", "JP", "KR", "US", "GB", "DE", "SA"])
            country_to = "ID"
            purpose = random.choice(PURPOSES_ARRIVAL[:2])
        else:
            country_from = nat_code
            country_to = "ID"
            purpose = random.choice(PURPOSES_ARRIVAL)

        duration = random.randint(3, 30) if nat_code != "ID" else None

        history.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "direction": "ARRIVAL",
            "port_of_entry": port,
            "visa_type": visa,
            "visa_number": f"VIS{random.randint(100000, 999999)}" if nat_code != "ID" else None,
            "purpose": purpose,
            "duration_days": duration,
            "flight_number": flight,
            "country_from": country_from,
            "country_to": country_to,
            "officer_notes": "",
        })

        # Departure (before arrival)
        depart_offset = random.randint(5, 45)
        depart_date = current_date - timedelta(days=depart_offset)

        if nat_code == "ID":
            country_from_dep = "ID"
            country_to_dep = history[-1]["country_from"]
            purpose_dep = random.choice(PURPOSES_DEPARTURE)
        else:
            country_from_dep = "ID"
            country_to_dep = nat_code
            purpose_dep = "Kembali ke Negara Asal"

        history.append({
            "date": depart_date.strftime("%Y-%m-%d"),
            "direction": "DEPARTURE",
            "port_of_entry": port,
            "visa_type": visa,
            "visa_number": None,
            "purpose": purpose_dep,
            "duration_days": depart_offset,
            "flight_number": gen_flight_number(nat_code),
            "country_from": country_from_dep,
            "country_to": country_to_dep,
            "officer_notes": "",
        })

        current_date = depart_date - timedelta(days=random.randint(30, 180))

    # Sort descending by date
    history.sort(key=lambda x: x["date"], reverse=True)
    return history


def get_faker_for_nat(nat_code: str):
    mapping = {
        "ID": fake_id, "MY": fake_ms, "SG": fake_en,
        "AU": fake_au, "US": fake_en, "CN": fake_zh,
        "GB": fake_gb, "JP": fake_jp, "DE": fake_de,
        "NL": fake_nl, "KR": fake_ko, "SA": fake_sa,
        "IN": fake_en,
    }
    return mapping.get(nat_code, fake_en)


def get_malay_name(gender: str) -> str:
    if gender == "M":
        return random.choice(MALAY_MALE_NAMES)
    return random.choice(MALAY_FEMALE_NAMES)


def get_nat_name(nat_code: str) -> str:
    for code, name, _ in NATIONALITIES:
        if code == nat_code:
            return name
    return nat_code


def gen_passenger(nat_code: str) -> dict:
    faker = get_faker_for_nat(nat_code)

    gender = random.choice(["M", "F"])
    dob = faker.date_of_birth(minimum_age=18, maximum_age=75)
    issue_date = date.today() - timedelta(days=random.randint(30, 1825))
    expiry_date = issue_date + timedelta(days=5 * 365)
    updated = datetime.now() - timedelta(days=random.randint(0, 365))

    if nat_code == "ID":
        city = fake_id.city()
        address = fake_id.address()
    else:
        city = faker.city()
        address = faker.address()

    # Gunakan nama Melayu dari pool khusus untuk Malaysia
    if nat_code == "MY":
        full_name = get_malay_name(gender)
    else:
        full_name = faker.name()

    return {
        "passport_number": gen_passport(nat_code),
        "full_name": full_name,
        "nationality": nat_code,
        "nationality_name": get_nat_name(nat_code),
        "date_of_birth": dob.strftime("%Y-%m-%d"),
        "gender": gender,
        "place_of_birth": city,
        "passport_expiry": expiry_date.strftime("%Y-%m-%d"),
        "passport_issue_date": issue_date.strftime("%Y-%m-%d"),
        "passport_issue_place": city,
        "occupation": random.choice(OCCUPATIONS),
        "address": address.replace("\n", ", "),
        "photo_url": None,
        "travel_history": gen_travel_history(nat_code, n=random.randint(2, 5)),
        "created_at": (updated - timedelta(days=random.randint(30, 730))).isoformat(),
        "updated_at": updated.isoformat(),
    }


# ─── Hardcoded passenger records untuk orang yang ada di blacklist ───────────
BLACKLISTED_PASSENGERS = [
    {
        "passport_number": "X8891234",
        "full_name": "Ridwan Kamali",
        "nationality": "ID", "nationality_name": "Indonesia",
        "date_of_birth": "1975-02-28", "gender": "M",
        "place_of_birth": "Makassar",
        "passport_expiry": "2028-03-10", "passport_issue_date": "2023-03-10",
        "passport_issue_place": "Makassar", "occupation": "Wiraswasta",
        "address": "Jl. Veteran No. 12, Makassar, Sulawesi Selatan",
        "photo_url": None,
        "travel_history": gen_travel_history("ID", n=2),
        "created_at": "2022-01-05T08:00:00", "updated_at": "2023-08-14T22:00:00",
    },
    {
        "passport_number": "MYA773421",
        "full_name": "Ahmad Nazri bin Osman",
        "nationality": "MY", "nationality_name": "Malaysia",
        "date_of_birth": "1978-03-15", "gender": "M",
        "place_of_birth": "Kuala Lumpur",
        "passport_expiry": "2027-06-20", "passport_issue_date": "2022-06-20",
        "passport_issue_place": "Kuala Lumpur", "occupation": "Swasta",
        "address": "Jalan Ampang, Kuala Lumpur, Malaysia",
        "photo_url": None,
        "travel_history": gen_travel_history("MY", n=3),
        "created_at": "2022-06-20T09:00:00", "updated_at": "2024-01-09T20:00:00",
    },
    {
        "passport_number": "US92847561",
        "full_name": "Daniel Ray Kowalski",
        "nationality": "US", "nationality_name": "Amerika Serikat",
        "date_of_birth": "1979-06-15", "gender": "M",
        "place_of_birth": "Chicago",
        "passport_expiry": "2029-04-10", "passport_issue_date": "2024-04-10",
        "passport_issue_place": "Chicago", "occupation": "Pedagang",
        "address": "123 Michigan Ave, Chicago, IL, USA",
        "photo_url": None,
        "travel_history": gen_travel_history("US", n=2),
        "created_at": "2021-01-10T10:00:00", "updated_at": "2022-05-19T15:00:00",
    },
    {
        "passport_number": "CN44219876",
        "full_name": "Zhou Meng",
        "nationality": "CN", "nationality_name": "Tiongkok",
        "date_of_birth": "1984-02-11", "gender": "M",
        "place_of_birth": "Guangzhou",
        "passport_expiry": "2028-09-15", "passport_issue_date": "2023-09-15",
        "passport_issue_place": "Guangzhou", "occupation": "Pengusaha",
        "address": "Tianhe District, Guangzhou, Guangdong, China",
        "photo_url": None,
        "travel_history": gen_travel_history("CN", n=3),
        "created_at": "2021-05-01T08:00:00", "updated_at": "2024-02-28T16:00:00",
    },
    {
        "passport_number": "B2291847",
        "full_name": "Siti Mardiyah",
        "nationality": "ID", "nationality_name": "Indonesia",
        "date_of_birth": "1988-01-30", "gender": "F",
        "place_of_birth": "Brebes",
        "passport_expiry": "2027-05-12", "passport_issue_date": "2022-05-12",
        "passport_issue_place": "Tegal", "occupation": "Ibu Rumah Tangga",
        "address": "Desa Paguyangan RT 02/03, Brebes, Jawa Tengah",
        "photo_url": None,
        "travel_history": gen_travel_history("ID", n=2),
        "created_at": "2020-05-12T07:00:00", "updated_at": "2023-11-04T10:00:00",
    },
    {
        "passport_number": "SG77281934",
        "full_name": "Lim Boon Keng",
        "nationality": "SG", "nationality_name": "Singapura",
        "date_of_birth": "1977-09-03", "gender": "M",
        "place_of_birth": "Singapore",
        "passport_expiry": "2026-11-20", "passport_issue_date": "2021-11-20",
        "passport_issue_place": "Singapore", "occupation": "Agen Tenaga Kerja",
        "address": "21 Orchard Road, Singapore 238883",
        "photo_url": None,
        "travel_history": gen_travel_history("SG", n=4),
        "created_at": "2021-11-20T08:00:00", "updated_at": "2024-02-13T18:00:00",
    },
    {
        "passport_number": "AU89712345",
        "full_name": "Michael Brett Lawson",
        "nationality": "AU", "nationality_name": "Australia",
        "date_of_birth": "1971-05-22", "gender": "M",
        "place_of_birth": "Melbourne",
        "passport_expiry": "2028-07-15", "passport_issue_date": "2023-07-15",
        "passport_issue_place": "Melbourne", "occupation": "Tidak Diketahui",
        "address": "Collins Street, Melbourne VIC 3000, Australia",
        "photo_url": None,
        "travel_history": gen_travel_history("AU", n=2),
        "created_at": "2022-01-01T00:00:00", "updated_at": "2023-05-31T20:00:00",
    },
    {
        "passport_number": "SA11239847",
        "full_name": "Khalid Al-Mansouri",
        "nationality": "SA", "nationality_name": "Arab Saudi",
        "date_of_birth": "1976-04-18", "gender": "M",
        "place_of_birth": "Riyadh",
        "passport_expiry": "2027-12-01", "passport_issue_date": "2022-12-01",
        "passport_issue_place": "Riyadh", "occupation": "Pengusaha",
        "address": "Al Olaya District, Riyadh 12333, Saudi Arabia",
        "photo_url": None,
        "travel_history": gen_travel_history("SA", n=3),
        "created_at": "2022-12-01T09:00:00", "updated_at": "2025-01-14T17:00:00",
    },
    {
        "passport_number": "C3312894",
        "full_name": "Hendra Gunawan",
        "nationality": "ID", "nationality_name": "Indonesia",
        "date_of_birth": "1983-06-25", "gender": "M",
        "place_of_birth": "Medan",
        "passport_expiry": "2027-08-10", "passport_issue_date": "2022-08-10",
        "passport_issue_place": "Medan", "occupation": "Wiraswasta",
        "address": "Jl. Gatot Subroto No. 88, Medan, Sumatera Utara",
        "photo_url": None,
        "travel_history": gen_travel_history("ID", n=2),
        "created_at": "2022-08-10T08:00:00", "updated_at": "2024-07-19T12:00:00",
    },
    {
        "passport_number": "NL88912345",
        "full_name": "Pieter Van Der Berg",
        "nationality": "NL", "nationality_name": "Belanda",
        "date_of_birth": "1968-03-12", "gender": "M",
        "place_of_birth": "Amsterdam",
        "passport_expiry": "2027-10-05", "passport_issue_date": "2022-10-05",
        "passport_issue_place": "Amsterdam", "occupation": "Pensiunan",
        "address": "Herengracht 44, 1015 Amsterdam, Netherlands",
        "photo_url": None,
        "travel_history": gen_travel_history("NL", n=2),
        "created_at": "2019-10-05T09:00:00", "updated_at": "2020-03-09T11:00:00",
    },
]


# ─── Hardcoded blacklist records ─────────────────────────────────────────────
BLACKLIST_RECORDS = [
    {
        "passport_number": "X8891234",
        "full_name": "Ridwan Kamali",
        "nationality": "ID",
        "date_of_birth": "1975-02-28",
        "severity": "CRITICAL",
        "reason_code": "DRUG_TRAFFICKING",
        "reason": "Terlibat jaringan penyelundupan narkoba internasional, tertangkap membawa 5kg methamphetamine di Bandara Soekarno-Hatta pada 2023.",
        "case_number": "IDN/2023/BNN/042",
        "referring_agency": "BNN",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2023-08-15",
        "expiry_date": None,
        "is_active": True,
        "notes": "Koordinasi dengan Interpol. Tangkap jika ditemukan.",
        "added_by": "sistem",
        "created_at": "2023-08-15T10:00:00",
    },
    {
        "passport_number": "MYA773421",
        "full_name": "Ahmad Nazri bin Osman",
        "nationality": "MY",
        "date_of_birth": "1978-03-15",
        "severity": "HIGH",
        "reason_code": "TERRORISM_SUPPORT",
        "reason": "Diduga memberikan dukungan logistik kepada kelompok ekstremis bersenjata. Masuk DPO Densus 88.",
        "case_number": "IDN/2024/DENSUS/017",
        "referring_agency": "Densus 88",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2024-01-10",
        "expiry_date": None,
        "is_active": True,
        "notes": "Koordinasi dengan Polis DiRaja Malaysia.",
        "added_by": "sistem",
        "created_at": "2024-01-10T08:30:00",
    },
    {
        "passport_number": "US92847561",
        "full_name": "Daniel Ray Kowalski",
        "nationality": "US",
        "date_of_birth": "1979-06-15",
        "severity": "MEDIUM",
        "reason_code": "FRAUD_IMMIGRATION",
        "reason": "Tertangkap menggunakan dokumen imigrasi palsu, deportasi ke AS pada 2022. Dilarang masuk selama 5 tahun.",
        "case_number": "IDN/2022/IMI/334",
        "referring_agency": "Ditjen Imigrasi",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2022-05-20",
        "expiry_date": "2027-05-20",
        "is_active": True,
        "notes": "Deportan. Dilarang masuk s/d 20 Mei 2027.",
        "added_by": "sistem",
        "created_at": "2022-05-20T14:00:00",
    },
    {
        "passport_number": "CN44219876",
        "full_name": "Zhou Meng",
        "nationality": "CN",
        "date_of_birth": "1984-02-11",
        "severity": "HIGH",
        "reason_code": "SMUGGLING",
        "reason": "Terlibat penyelundupan satwa liar dilindungi dan barang elektronik ilegal bernilai miliaran rupiah.",
        "case_number": "IDN/2024/PPNS/091",
        "referring_agency": "KLHK",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2024-03-01",
        "expiry_date": None,
        "is_active": True,
        "notes": "Koordinasi dengan Bea Cukai dan KLHK.",
        "added_by": "sistem",
        "created_at": "2024-03-01T09:00:00",
    },
    {
        "passport_number": "B2291847",
        "full_name": "Siti Mardiyah",
        "nationality": "ID",
        "date_of_birth": "1988-01-30",
        "severity": "LOW",
        "reason_code": "VISA_OVERSTAY_REPEAT",
        "reason": "Overstay visa kerja di Arab Saudi sebanyak 3 kali. Terdeteksi kembali mencoba berangkat dengan dokumen tidak lengkap.",
        "case_number": "IDN/2023/IMI/891",
        "referring_agency": "Ditjen Imigrasi",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2023-11-05",
        "expiry_date": "2025-11-05",
        "is_active": True,
        "notes": "Wajib melapor ke Kantor Imigrasi setempat.",
        "added_by": "sistem",
        "created_at": "2023-11-05T11:00:00",
    },
    {
        "passport_number": "SG77281934",
        "full_name": "Lim Boon Keng",
        "nationality": "SG",
        "date_of_birth": "1977-09-03",
        "severity": "MEDIUM",
        "reason_code": "HUMAN_TRAFFICKING",
        "reason": "Dicurigai terlibat jaringan perdagangan orang, merekrut korban dengan modus lowongan kerja palsu.",
        "case_number": "IDN/2024/BPMI/022",
        "referring_agency": "BP2MI",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2024-02-14",
        "expiry_date": None,
        "is_active": True,
        "notes": "Dalam penyelidikan bersama IOM.",
        "added_by": "sistem",
        "created_at": "2024-02-14T13:30:00",
    },
    {
        "passport_number": "AU89712345",
        "full_name": "Michael Brett Lawson",
        "nationality": "AU",
        "date_of_birth": "1971-05-22",
        "severity": "CRITICAL",
        "reason_code": "CHILD_EXPLOITATION",
        "reason": "Masuk daftar hitam Interpol atas kasus eksploitasi seksual anak. Warran penangkapan internasional aktif.",
        "case_number": "INTERPOL/2023/RED/4421",
        "referring_agency": "Interpol",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2023-06-01",
        "expiry_date": None,
        "is_active": True,
        "notes": "DARURAT - Hubungi Densus 88 segera jika ditemukan. Red Notice Interpol aktif.",
        "added_by": "sistem",
        "created_at": "2023-06-01T07:00:00",
    },
    {
        "passport_number": "SA11239847",
        "full_name": "Khalid Al-Mansouri",
        "nationality": "SA",
        "date_of_birth": "1976-04-18",
        "severity": "HIGH",
        "reason_code": "TERRORISM_FINANCING",
        "reason": "Terindikasi mentransfer dana kepada jaringan teroris melalui jalur hawala. Dalam investigasi bersama PPATK.",
        "case_number": "IDN/2025/BNPT/008",
        "referring_agency": "BNPT",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2025-01-15",
        "expiry_date": None,
        "is_active": True,
        "notes": "Koordinasi dengan PPATK dan Kemenkeu.",
        "added_by": "sistem",
        "created_at": "2025-01-15T08:00:00",
    },
    {
        "passport_number": "C3312894",
        "full_name": "Hendra Gunawan",
        "nationality": "ID",
        "date_of_birth": "1983-06-25",
        "severity": "MEDIUM",
        "reason_code": "DRUG_POSSESSION",
        "reason": "Tertangkap membawa sabu 50 gram dari Malaysia. Sedang dalam proses persidangan.",
        "case_number": "IDN/2024/BNN/187",
        "referring_agency": "BNN",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2024-07-20",
        "expiry_date": None,
        "is_active": True,
        "notes": "Paspor disita. Dilarang bepergian ke luar negeri.",
        "added_by": "sistem",
        "created_at": "2024-07-20T10:30:00",
    },
    {
        "passport_number": "NL88912345",
        "full_name": "Pieter Van Der Berg",
        "nationality": "NL",
        "date_of_birth": "1968-03-12",
        "severity": "LOW",
        "reason_code": "DEPORTEE_PROHIBITED",
        "reason": "Dideportasi pada 2020 akibat pelanggaran visa kerja. Larangan masuk telah berakhir.",
        "case_number": "IDN/2020/IMI/445",
        "referring_agency": "Ditjen Imigrasi",
        "issuing_authority": "Ditjen Imigrasi",
        "blacklist_date": "2020-03-10",
        "expiry_date": "2025-03-10",
        "is_active": False,
        "notes": "Blacklist sudah tidak aktif. Dapat masuk kembali dengan visa yang valid.",
        "added_by": "sistem",
        "created_at": "2020-03-10T09:00:00",
    },
]


def generate_passengers(count: int = 200) -> list:
    """Generate `count` passenger records using weighted nationality distribution.
    Selalu menyertakan BLACKLISTED_PASSENGERS agar dapat ditemukan saat pencarian."""
    weights = [w for _, _, w in NATIONALITIES]
    nat_codes = [code for code, _, _ in NATIONALITIES]

    passengers = []
    # Mulai dengan passport yang sudah ada di blacklist (agar bisa dicari)
    seen_passports = {p["passport_number"] for p in BLACKLISTED_PASSENGERS}
    passengers.extend(BLACKLISTED_PASSENGERS)

    attempts = 0
    target = count - len(BLACKLISTED_PASSENGERS)
    while len(passengers) < count and attempts < target * 3:
        attempts += 1
        nat_code = random.choices(nat_codes, weights=weights, k=1)[0]
        passenger = gen_passenger(nat_code)

        # Ensure unique passport numbers
        if passenger["passport_number"] in seen_passports:
            continue

        seen_passports.add(passenger["passport_number"])
        passengers.append(passenger)

    return passengers


def delete_existing_passengers(es):
    """Delete all passenger documents."""
    try:
        es.delete_by_query(
            index=Config.INDEX_PASSENGERS,
            body={"query": {"match_all": {}}},
            refresh=True,
        )
        print("  [OK]    Data penumpang lama dihapus.")
    except Exception as e:
        print(f"  [WARN]  Gagal hapus data lama: {e}")


def index_passengers(es, passengers: list, dry_run: bool = False) -> int:
    if dry_run:
        return len(passengers)

    actions = [
        {
            "_index": Config.INDEX_PASSENGERS,
            "_id": p["passport_number"],
            "_source": p,
        }
        for p in passengers
    ]

    success, errors = bulk(es, actions, raise_on_error=False)
    if errors:
        print(f"  [WARN]  {len(errors)} dokumen gagal diindeks.")
    return success


def index_blacklist(es, records: list, dry_run: bool = False) -> int:
    if dry_run:
        return len(records)

    # Delete existing blacklist first
    try:
        es.delete_by_query(
            index=Config.INDEX_BLACKLIST,
            body={"query": {"match_all": {}}},
            refresh=True,
        )
    except Exception:
        pass

    actions = [
        {
            "_index": Config.INDEX_BLACKLIST,
            "_source": r,
        }
        for r in records
    ]

    success, errors = bulk(es, actions, raise_on_error=False)
    if errors:
        print(f"  [WARN]  {len(errors)} blacklist gagal diindeks.")
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Load dummy data ke Elasticsearch untuk Checkpoint Imigrasi"
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Hapus semua data penumpang lama sebelum load"
    )
    parser.add_argument(
        "--add", type=int, metavar="N",
        help="Tambah N penumpang baru (tanpa menghapus yang ada)"
    )
    parser.add_argument(
        "--count", type=int, default=200,
        help="Jumlah penumpang yang dibuat (default: 200)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate data tapi tidak dikirim ke Elasticsearch"
    )
    parser.add_argument(
        "--output", type=str,
        help="Simpan data ke file JSON (gunakan dengan --dry-run)"
    )
    args = parser.parse_args()

    print("\n=== Checkpoint Imigrasi - Dummy Data Loader ===\n")

    count = args.add if args.add else args.count
    dry_run = args.dry_run

    print(f"  Membuat {count} data penumpang...")
    passengers = generate_passengers(count)
    print(f"  {len(passengers)} penumpang berhasil digenerate.")

    if dry_run:
        output_data = {
            "passengers": passengers,
            "blacklist": BLACKLIST_RECORDS,
        }
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\n  [OK]    Data disimpan ke: {args.output}")
        else:
            print(json.dumps(output_data, ensure_ascii=False, indent=2)[:3000])
            print("  ... (output dipotong untuk preview)")
        return

    print(f"\n  Menghubungi Elasticsearch: {Config.ES_URL}")
    try:
        es = get_es_client()
        es.info()
        print("  Terhubung ke Elasticsearch.\n")
    except Exception as e:
        print(f"  [ERROR] Gagal terhubung: {e}")
        sys.exit(1)

    # Check if indices exist
    for idx in [Config.INDEX_PASSENGERS, Config.INDEX_BLACKLIST]:
        if not es.indices.exists(index=idx):
            print(f"  [ERROR] Index '{idx}' tidak ditemukan. Jalankan create_indices.py terlebih dahulu.")
            sys.exit(1)

    if args.fresh:
        print("  [FRESH] Menghapus data penumpang lama...")
        delete_existing_passengers(es)

    print(f"  Mengindeks {len(passengers)} penumpang...")
    ok = index_passengers(es, passengers)
    print(f"  [OK]    {ok} penumpang berhasil diindeks ke '{Config.INDEX_PASSENGERS}'.")

    if not args.add:
        print(f"\n  Mengindeks {len(BLACKLIST_RECORDS)} blacklist records...")
        ok_bl = index_blacklist(es, BLACKLIST_RECORDS)
        print(f"  [OK]    {ok_bl} records berhasil diindeks ke '{Config.INDEX_BLACKLIST}'.")

    print("\n=== Selesai ===")
    print(f"  Total penumpang diindeks : {len(passengers)}")
    if not args.add:
        print(f"  Total blacklist diindeks : {len(BLACKLIST_RECORDS)}")
    print("\nJalankan 'python app.py' untuk memulai aplikasi.\n")


if __name__ == "__main__":
    main()
