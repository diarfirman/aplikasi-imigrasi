from flask import Blueprint, render_template, request, flash
from services.search_service import search_passengers, looks_like_passport
from services.blacklist_service import check_blacklist

search_bp = Blueprint("search", __name__)

NATIONALITY_LABELS = {
    "ID": "Indonesia", "MY": "Malaysia", "SG": "Singapura",
    "AU": "Australia", "US": "Amerika Serikat", "CN": "Tiongkok",
    "GB": "Inggris", "JP": "Jepang", "DE": "Jerman",
    "NL": "Belanda", "SA": "Arab Saudi", "KR": "Korea Selatan",
    "IN": "India",
}


@search_bp.route("/")
def index():
    return render_template("index.html")


@search_bp.route("/search", methods=["POST"])
def search():
    query = request.form.get("query", "").strip()
    search_type = request.form.get("search_type", "auto")

    # Filter tambahan (opsional)
    gender = request.form.get("gender", "").strip() or None
    date_of_birth = request.form.get("date_of_birth", "").strip() or None
    nationality = request.form.get("nationality", "").strip() or None

    if not query:
        flash("Masukkan nomor paspor atau nama untuk pencarian.", "warning")
        return render_template("index.html")

    try:
        passengers = search_passengers(
            query,
            search_type,
            gender=gender,
            date_of_birth=date_of_birth,
            nationality=nationality,
        )
    except RuntimeError as e:
        flash(str(e), "danger")
        return render_template("index.html")

    # Cek blacklist untuk setiap hasil
    results = []
    for p in passengers:
        blacklist_entry = check_blacklist(
            passport_number=p.get("passport_number"),
            full_name=p.get("full_name"),
            date_of_birth=p.get("date_of_birth"),
        )
        results.append({
            "passenger": p,
            "blacklist": blacklist_entry,
        })

    if search_type == "auto":
        detected_type = "passport" if looks_like_passport(query) else "name"
    else:
        detected_type = search_type

    # Ringkasan filter aktif untuk ditampilkan di hasil
    active_filters = {}
    if gender:
        active_filters["Jenis Kelamin"] = "Laki-laki" if gender == "M" else "Perempuan"
    if date_of_birth:
        active_filters["Tanggal Lahir"] = date_of_birth
    if nationality:
        active_filters["Kebangsaan"] = NATIONALITY_LABELS.get(nationality.upper(), nationality)

    return render_template(
        "results.html",
        results=results,
        query=query,
        search_type=search_type,
        detected_type=detected_type,
        total=len(results),
        active_filters=active_filters,
    )
