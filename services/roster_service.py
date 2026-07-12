from datetime import date, timedelta
import calendar
from database import firestore_db as db
from services.holiday_service import is_holiday_or_friday


def get_days_in_month(year, month):
    num_days = calendar.monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, num_days + 1)]


def get_next_pharmacist_index(muni_id, shift_type, month_start, pharmacists):
    if not pharmacists:
        return 0

    last_duty = db.get_last_duty_schedule(muni_id, shift_type, month_start)

    if not last_duty:
        return 0

    last_ph_id = last_duty.pharmacist_id

    for idx, p in enumerate(pharmacists):
        if p.id == last_ph_id:
            return (idx + 1) % len(pharmacists)

    last_ph = db.get_pharmacist_by_id(last_ph_id)
    if last_ph:
        last_ph_order = last_ph.rotation_order
        for idx, p in enumerate(pharmacists):
            if p.rotation_order > last_ph_order:
                return idx

    return 0


def is_on_vacation(ph_id, day):
    v = db.get_vacations_for_pharmacist_in_range(ph_id, day, day)
    return v is not None


def is_already_assigned(ph_id, day, muni_id):
    duty = db.get_duty_by_date_muni_pharmacist(day, ph_id, muni_id)
    return duty is not None


def generate_roster(year, month, daira_id):
    month_start = date(year, month, 1)
    days = get_days_in_month(year, month)

    municipalities = db.get_municipalities_by_daira(str(daira_id))

    all_new_duties = []

    for muni in municipalities:
        pharmacists = db.get_pharmacists_by_municipality(muni.id, active_only=True)

        if not pharmacists:
            continue

        num_phs = len(pharmacists)

        if num_phs > 4:
            night_idx = get_next_pharmacist_index(muni.id, 'NIGHT', month_start, pharmacists)

            for d in days:
                existing_night = db.get_duty_by_date_muni_shift(d, muni.id, 'NIGHT')
                if not existing_night:
                    attempts = 0
                    while (is_on_vacation(pharmacists[night_idx].id, d) or is_already_assigned(pharmacists[night_idx].id, d, muni.id)) and attempts < num_phs:
                        night_idx = (night_idx + 1) % num_phs
                        attempts += 1

                    all_new_duties.append({
                        "date": d.isoformat(),
                        "pharmacist_id": pharmacists[night_idx].id,
                        "municipality_id": muni.id,
                        "shift_type": "NIGHT",
                        "is_holiday": is_holiday_or_friday(d),
                    })
                    night_idx = (night_idx + 1) % num_phs

        holiday_days = [d for d in days if is_holiday_or_friday(d)]
        day_idx = get_next_pharmacist_index(muni.id, 'HOLIDAY_DAY', month_start, pharmacists)

        for d in holiday_days:
            existing_day = db.get_duty_by_date_muni_shift(d, muni.id, 'HOLIDAY_DAY')
            if not existing_day:
                attempts = 0
                while (is_on_vacation(pharmacists[day_idx].id, d) or is_already_assigned(pharmacists[day_idx].id, d, muni.id)) and attempts < num_phs:
                    day_idx = (day_idx + 1) % num_phs
                    attempts += 1

                all_new_duties.append({
                    "date": d.isoformat(),
                    "pharmacist_id": pharmacists[day_idx].id,
                    "municipality_id": muni.id,
                    "shift_type": "HOLIDAY_DAY",
                    "is_holiday": True,
                })
                day_idx = (day_idx + 1) % num_phs

    if all_new_duties:
        db.batch_create_duties(all_new_duties)


def get_roster_data(year, month, daira_id):
    return db.get_duties_for_month(year, month, daira_id)
