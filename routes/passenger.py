from flask import Blueprint, render_template, abort
from services.passenger_service import (
    get_passenger,
    get_travel_history_sorted,
    get_nationality_flag,
    format_date_display,
)
from services.blacklist_service import (
    check_blacklist,
    get_severity_label,
    get_reason_label,
)

passenger_bp = Blueprint("passenger", __name__)


@passenger_bp.route("/<passport_number>")
def detail(passport_number):
    passenger = get_passenger(passport_number)
    if not passenger:
        abort(404)

    blacklist_entry = check_blacklist(
        passport_number=passenger.get("passport_number"),
        full_name=passenger.get("full_name"),
        date_of_birth=passenger.get("date_of_birth"),
    )

    travel_history = get_travel_history_sorted(passenger)
    flag = get_nationality_flag(passenger.get("nationality", ""))

    return render_template(
        "passenger_detail.html",
        passenger=passenger,
        blacklist=blacklist_entry,
        travel_history=travel_history,
        flag=flag,
        format_date=format_date_display,
        severity_label=get_severity_label,
        reason_label=get_reason_label,
    )
