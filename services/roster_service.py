from datetime import date
import calendar
from database import firestore_db as db
from services.holiday_service import is_holiday_or_friday


def get_days_in_month(year, month):
    num_days = calendar.monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, num_days + 1)]


def generate_roster(year, month, daira_id, cached=None):
    month_start = date(year, month, 1)
    days = get_days_in_month(year, month)

    municipalities = db.get_municipalities_by_daira(str(daira_id))
    if not municipalities:
        return

    if cached:
        all_pharmacists = cached["pharmacists"]
        all_vacations = cached["vacations"]
        prev_duties = cached["prev_duties"]
        existing_duties = cached["existing_duties"]
    else:
        all_pharmacists = db.get_all_pharmacists_dict()
        all_vacations = db.get_all_vacations_dict()
        existing_duties = db.get_duties_for_month_bulk(year, month)
        prev_duties = db.get_all_duties_before_bulk(month_start.isoformat())

    existing_keys = set()
    for d in existing_duties:
        existing_keys.add((d.date.isoformat(), d.municipality_id, d.shift_type))

    assigned_today = {}
    for d in existing_duties:
        key = (d.date.isoformat(), d.pharmacist_id, d.municipality_id)
        assigned_today[key] = True

    all_new_duties = []

    for muni in municipalities:
        muni_ph_ids = [p_id for p_id, p in all_pharmacists.items()
                       if p.municipality_id == muni.id and p.is_active]
        pharmacists = sorted(
            [all_pharmacists[pid] for pid in muni_ph_ids],
            key=lambda p: p.rotation_order
        )

        if not pharmacists:
            continue

        num_phs = len(pharmacists)

        def is_on_vacation_local(ph_id, day):
            vacs = all_vacations.get(ph_id, [])
            for v in vacs:
                if v.start_date <= day <= v.end_date:
                    return True
            return False

        def is_already_assigned_local(ph_id, day, muni_id):
            return (day.isoformat(), ph_id, muni_id) in assigned_today

        def get_next_index_local(muni_id, shift_type):
            last = None
            for d in sorted(prev_duties, key=lambda x: x.date, reverse=True):
                if d.municipality_id == muni_id and d.shift_type == shift_type:
                    last = d
                    break

            if not last:
                return 0

            last_ph_id = last.pharmacist_id
            for idx, p in enumerate(pharmacists):
                if p.id == last_ph_id:
                    return (idx + 1) % num_phs

            return 0

        if num_phs > 4:
            night_idx = get_next_index_local(muni.id, 'NIGHT')

            for d in days:
                key = (d.isoformat(), muni.id, 'NIGHT')
                if key not in existing_keys:
                    attempts = 0
                    while (is_on_vacation_local(pharmacists[night_idx].id, d) or
                           is_already_assigned_local(pharmacists[night_idx].id, d, muni.id)) and attempts < num_phs:
                        night_idx = (night_idx + 1) % num_phs
                        attempts += 1

                    new_duty = {
                        "date": d.isoformat(),
                        "pharmacist_id": pharmacists[night_idx].id,
                        "municipality_id": muni.id,
                        "shift_type": "NIGHT",
                        "is_holiday": is_holiday_or_friday(d),
                    }
                    all_new_duties.append(new_duty)
                    assigned_today[(d.isoformat(), pharmacists[night_idx].id, muni.id)] = True
                    night_idx = (night_idx + 1) % num_phs

        holiday_days = [d for d in days if is_holiday_or_friday(d)]
        day_idx = get_next_index_local(muni.id, 'HOLIDAY_DAY')

        for d in holiday_days:
            key = (d.isoformat(), muni.id, 'HOLIDAY_DAY')
            if key not in existing_keys:
                attempts = 0
                while (is_on_vacation_local(pharmacists[day_idx].id, d) or
                       is_already_assigned_local(pharmacists[day_idx].id, d, muni.id)) and attempts < num_phs:
                    day_idx = (day_idx + 1) % num_phs
                    attempts += 1

                new_duty = {
                    "date": d.isoformat(),
                    "pharmacist_id": pharmacists[day_idx].id,
                    "municipality_id": muni.id,
                    "shift_type": "HOLIDAY_DAY",
                    "is_holiday": True,
                }
                all_new_duties.append(new_duty)
                assigned_today[(d.isoformat(), pharmacists[day_idx].id, muni.id)] = True
                day_idx = (day_idx + 1) % num_phs

    if all_new_duties:
        db.batch_create_duties(all_new_duties)


def generate_roster_cached(year, month, daira_ids):
    month_start = date(year, month, 1)

    all_pharmacists = db.get_all_pharmacists_dict()
    all_vacations = db.get_all_vacations_dict()
    existing_duties = db.get_duties_for_month_bulk(year, month)
    prev_duties = db.get_all_duties_before_bulk(month_start.isoformat())

    cached = {
        "pharmacists": all_pharmacists,
        "vacations": all_vacations,
        "existing_duties": existing_duties,
        "prev_duties": prev_duties,
    }

    for daira_id in daira_ids:
        generate_roster(year, month, daira_id, cached=cached)

    return cached


def get_roster_data(year, month, daira_id):
    return db.get_duties_for_month(year, month, daira_id)
