from datetime import date
from flask import Blueprint, render_template, request, flash, redirect, url_for
from services.blacklist_service import add_to_blacklist

admin_bp = Blueprint("admin", __name__)

REASON_CODES = [
    ("DRUG_TRAFFICKING", "Penyelundupan Narkoba"),
    ("DRUG_POSSESSION", "Kepemilikan Narkoba"),
    ("TERRORISM_SUPPORT", "Dukungan Terorisme"),
    ("TERRORISM_FINANCING", "Pendanaan Terorisme"),
    ("HUMAN_TRAFFICKING", "Perdagangan Manusia"),
    ("SMUGGLING", "Penyelundupan Barang"),
    ("FRAUD_IMMIGRATION", "Penipuan Imigrasi"),
    ("CHILD_EXPLOITATION", "Eksploitasi Anak"),
    ("DEPORTEE_PROHIBITED", "Deportan Terlarang"),
    ("VISA_OVERSTAY_REPEAT", "Overstay Berulang"),
    ("WANTED_FOREIGN", "DPO Asing"),
    ("MONEY_LAUNDERING", "Pencucian Uang"),
    ("OTHER", "Lainnya"),
]

NATIONALITIES = [
    ("ID", "Indonesia"), ("MY", "Malaysia"), ("SG", "Singapura"),
    ("AU", "Australia"), ("US", "Amerika Serikat"), ("CN", "Tiongkok"),
    ("GB", "Inggris"), ("JP", "Jepang"), ("DE", "Jerman"),
    ("NL", "Belanda"), ("SA", "Arab Saudi"), ("KR", "Korea Selatan"),
    ("IN", "India"), ("FR", "Prancis"), ("IT", "Italia"),
    ("OTHER", "Lainnya"),
]

SEVERITIES = [
    ("LOW", "Rendah (LOW)"),
    ("MEDIUM", "Sedang (MEDIUM)"),
    ("HIGH", "Tinggi (HIGH)"),
    ("CRITICAL", "Kritis (CRITICAL)"),
]

AGENCIES = [
    "Ditjen Imigrasi", "BNN", "Polri", "Densus 88", "BNPT",
    "BP2MI", "KLHK", "PPATK", "Interpol", "Kemenkeu", "Lainnya",
]


@admin_bp.route("/blacklist", methods=["GET"])
def blacklist_form():
    return render_template(
        "admin/blacklist.html",
        reason_codes=REASON_CODES,
        nationalities=NATIONALITIES,
        severities=SEVERITIES,
        agencies=AGENCIES,
        today=date.today().isoformat(),
    )


@admin_bp.route("/blacklist", methods=["POST"])
def blacklist_submit():
    data = {
        "passport_number": request.form.get("passport_number", "").strip().upper(),
        "full_name": request.form.get("full_name", "").strip(),
        "nationality": request.form.get("nationality", "").strip(),
        "date_of_birth": request.form.get("date_of_birth", "").strip() or None,
        "severity": request.form.get("severity", "MEDIUM"),
        "reason_code": request.form.get("reason_code", "OTHER"),
        "reason": request.form.get("reason", "").strip(),
        "case_number": request.form.get("case_number", "").strip() or None,
        "referring_agency": request.form.get("referring_agency", "").strip() or None,
        "issuing_authority": request.form.get("issuing_authority", "Ditjen Imigrasi"),
        "blacklist_date": request.form.get("blacklist_date", "").strip() or None,
        "expiry_date": request.form.get("expiry_date", "").strip() or None,
        "notes": request.form.get("notes", "").strip() or None,
        "added_by": "petugas-admin",
    }

    if not data["passport_number"] and not data["full_name"]:
        flash("Nomor paspor atau nama lengkap wajib diisi.", "danger")
        return redirect(url_for("admin.blacklist_form"))

    if not data["full_name"]:
        flash("Nama lengkap wajib diisi.", "danger")
        return redirect(url_for("admin.blacklist_form"))

    if not data["date_of_birth"]:
        flash("Tanggal lahir wajib diisi untuk mencegah false positif.", "danger")
        return redirect(url_for("admin.blacklist_form"))

    try:
        add_to_blacklist(data)
        flash(
            f"Berhasil menambahkan '{data['full_name']}' ke daftar cekal.",
            "success",
        )
        return render_template("admin/blacklist_success.html", data=data)
    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("admin.blacklist_form"))
