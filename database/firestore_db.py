import os
import json
from datetime import date
from google.cloud import firestore
from models import Daira, Municipality, Pharmacist, Vacation, DutySchedule, User

_db = None


def get_db():
    global _db
    if _db is None:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.isfile(cred_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

        info_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if info_json:
            info = json.loads(info_json)
            _db = firestore.Client.from_service_account_info(info, project=info.get("project_id"))
        else:
            _db = firestore.Client()
    return _db


COLLECTIONS = {
    "daira": "dairas",
    "municipality": "municipalities",
    "pharmacist": "pharmacists",
    "vacation": "vacations",
    "duty_schedule": "duty_schedules",
    "user": "users",
}


def _col(name):
    return get_db().collection(COLLECTIONS[name])


def _add(name, data: dict) -> str:
    ref = _col(name).add(data)
    return ref[1].id


def _get(name, doc_id: str) -> dict | None:
    doc = _col(name).document(doc_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def _update(name, doc_id: str, data: dict):
    _col(name).document(doc_id).update(data)


def _delete(name, doc_id: str):
    _col(name).document(doc_id).delete()


def _query(name, filters=None, order_by=None, limit=None):
    q = _col(name)
    if filters:
        for field_name, op, value in filters:
            q = q.where(field_name, op, value)
    if order_by:
        desc = order_by.startswith("-")
        field_name = order_by.lstrip("-")
        q = q.order_by(field_name, direction=firestore.Query.DESCENDING if desc else firestore.Query.ASCENDING)
    if limit:
        q = q.limit(limit)
    return q.stream()


def _query_all(name, filters=None):
    docs = list(_query(name, filters))
    return [(d.id, d.to_dict()) for d in docs]


# --- DAIRA ---

def get_daira(doc_id: str) -> Daira | None:
    data = _get("daira", doc_id)
    if data:
        return Daira.from_dict(doc_id, data)
    return None


def get_all_dairas() -> list[Daira]:
    docs = list(_col("daira").stream())
    return [Daira.from_dict(d.id, d.to_dict()) for d in docs]


def create_daira(name_ar: str, name_fr: str) -> Daira:
    doc_id = _add("daira", {"name_ar": name_ar, "name_fr": name_fr})
    return Daira(id=doc_id, name_ar=name_ar, name_fr=name_fr)


def update_daira(doc_id: str, name_ar: str = None, name_fr: str = None):
    data = {}
    if name_ar is not None:
        data["name_ar"] = name_ar
    if name_fr is not None:
        data["name_fr"] = name_fr
    if data:
        _update("daira", doc_id, data)


def delete_daira(doc_id: str):
    municipalities = get_municipalities_by_daira(doc_id)
    for m in municipalities:
        delete_municipality(m.id)
    _delete("daira", doc_id)


# --- MUNICIPALITY ---

def get_municipality(doc_id: str) -> Municipality | None:
    data = _get("municipality", doc_id)
    if data:
        return Municipality.from_dict(doc_id, data)
    return None


def get_municipalities_by_daira(daira_id: str) -> list[Municipality]:
    docs = _query_all("municipality", [("daira_id", "==", daira_id)])
    return [Municipality.from_dict(did, d) for did, d in docs]


def get_all_municipalities() -> list[Municipality]:
    docs = list(_col("municipality").stream())
    return [Municipality.from_dict(d.id, d.to_dict()) for d in docs]


def create_municipality(name_ar: str, name_fr: str, daira_id: str) -> Municipality:
    doc_id = _add("municipality", {"name_ar": name_ar, "name_fr": name_fr, "daira_id": daira_id})
    return Municipality(id=doc_id, name_ar=name_ar, name_fr=name_fr, daira_id=daira_id)


def update_municipality(doc_id: str, **kwargs):
    data = {k: v for k, v in kwargs.items() if v is not None}
    if data:
        _update("municipality", doc_id, data)


def delete_municipality(doc_id: str):
    pharmacists = get_pharmacists_by_municipality(doc_id)
    for p in pharmacists:
        delete_pharmacist(p.id)
    duties = get_duties_by_municipality(doc_id)
    for d in duties:
        _delete("duty_schedule", d.id)
    _delete("municipality", doc_id)


# --- PHARMACIST ---

def get_pharmacist(doc_id: str) -> Pharmacist | None:
    data = _get("pharmacist", doc_id)
    if data:
        return Pharmacist.from_dict(doc_id, data)
    return None


def get_pharmacists_by_municipality(municipality_id: str, active_only: bool = False) -> list[Pharmacist]:
    filters = [("municipality_id", "==", municipality_id)]
    if active_only:
        filters.append(("is_active", "==", True))
    docs = _query_all("pharmacist", filters)
    result = [Pharmacist.from_dict(did, d) for did, d in docs]
    result.sort(key=lambda p: p.rotation_order)
    return result


def get_all_pharmacists() -> list[Pharmacist]:
    docs = list(_col("pharmacist").stream())
    return [Pharmacist.from_dict(d.id, d.to_dict()) for d in docs]


def create_pharmacist(name_fr: str, municipality_id: str, address_fr: str = "",
                      rotation_order: int = 0, license_number: str = "",
                      is_active: bool = True) -> Pharmacist:
    data = {
        "name_fr": name_fr,
        "address_fr": address_fr,
        "municipality_id": municipality_id,
        "rotation_order": rotation_order,
        "license_number": license_number,
        "is_active": is_active,
    }
    doc_id = _add("pharmacist", data)
    return Pharmacist(id=doc_id, **data)


def update_pharmacist(doc_id: str, **kwargs):
    data = {k: v for k, v in kwargs.items() if v is not None}
    if data:
        _update("pharmacist", doc_id, data)


def delete_pharmacist(doc_id: str):
    vacations = get_vacations_by_pharmacist(doc_id)
    for v in vacations:
        _delete("vacation", v.id)
    duties = _query_all("duty_schedule", [("pharmacist_id", "==", doc_id)])
    for did, _ in duties:
        _delete("duty_schedule", did)
    _delete("pharmacist", doc_id)


# --- VACATION ---

def get_vacation(doc_id: str) -> Vacation | None:
    data = _get("vacation", doc_id)
    if data:
        return Vacation.from_dict(doc_id, data)
    return None


def get_vacations_by_pharmacist(pharmacist_id: str) -> list[Vacation]:
    docs = _query_all("vacation", [("pharmacist_id", "==", pharmacist_id)])
    return [Vacation.from_dict(did, d) for did, d in docs]


def create_vacation(pharmacist_id: str, start_date: date, end_date: date) -> Vacation:
    doc_id = _add("vacation", {
        "pharmacist_id": pharmacist_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })
    return Vacation(id=doc_id, pharmacist_id=pharmacist_id, start_date=start_date, end_date=end_date)


def delete_vacation(doc_id: str):
    _delete("vacation", doc_id)


# --- DUTY SCHEDULE ---

def get_duty(doc_id: str) -> DutySchedule | None:
    data = _get("duty_schedule", doc_id)
    if data:
        return DutySchedule.from_dict(doc_id, data)
    return None


def get_duties_by_municipality(municipality_id: str) -> list[DutySchedule]:
    docs = _query_all("duty_schedule", [("municipality_id", "==", municipality_id)])
    return [DutySchedule.from_dict(did, d) for did, d in docs]


def get_duties_for_month(year: int, month: int, daira_id: str = None) -> list[DutySchedule]:
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    if daira_id:
        municipalities = get_municipalities_by_daira(daira_id)
        muni_ids = {m.id for m in municipalities}
        docs = _query_all("duty_schedule", [("date", ">=", start_str), ("date", "<", end_str)])
        return [DutySchedule.from_dict(did, d) for did, d in docs if d.get("municipality_id") in muni_ids]
    else:
        docs = _query_all("duty_schedule", [("date", ">=", start_str), ("date", "<", end_str)])
        return [DutySchedule.from_dict(did, d) for did, d in docs]


def get_duties_for_month_by_daira(year: int, month: int, daira_id: str) -> list[DutySchedule]:
    return get_duties_for_month(year, month, daira_id)


def get_generated_months() -> list[dict]:
    docs = list(_col("duty_schedule").stream())
    months_set = set()
    for d in docs:
        data = d.to_dict()
        ds = data.get("date")
        if isinstance(ds, str):
            ds = date.fromisoformat(ds)
        if ds:
            months_set.add((ds.year, ds.month))
    result = [{"year": y, "month": m} for y, m in months_set]
    result.sort(key=lambda x: (-x["year"], -x["month"]))
    return result


def get_duty_by_date_muni_shift(date_val: date, municipality_id: str, shift_type: str) -> DutySchedule | None:
    date_str = date_val.isoformat() if isinstance(date_val, date) else date_val
    docs = _query_all("duty_schedule", [
        ("date", "==", date_str),
        ("municipality_id", "==", municipality_id),
        ("shift_type", "==", shift_type),
    ])
    if docs:
        return DutySchedule.from_dict(docs[0][0], docs[0][1])
    return None


def get_duty_by_date_muni_pharmacist(date_val: date, pharmacist_id: str, municipality_id: str) -> DutySchedule | None:
    date_str = date_val.isoformat() if isinstance(date_val, date) else date_val
    docs = _query_all("duty_schedule", [
        ("date", "==", date_str),
        ("pharmacist_id", "==", pharmacist_id),
        ("municipality_id", "==", municipality_id),
    ])
    if docs:
        return DutySchedule.from_dict(docs[0][0], docs[0][1])
    return None


def get_last_duty_schedule(municipality_id: str, shift_type: str, before_date: date) -> DutySchedule | None:
    date_str = before_date.isoformat() if isinstance(before_date, date) else before_date
    docs = _query_all("duty_schedule", [
        ("municipality_id", "==", municipality_id),
        ("shift_type", "==", shift_type),
        ("date", "<", date_str),
    ])
    result = []
    for did, d in docs:
        ds = DutySchedule.from_dict(did, d)
        if ds.date:
            result.append(ds)
    result.sort(key=lambda x: x.date, reverse=True)
    return result[0] if result else None


def get_pharmacist_by_id(ph_id: str) -> Pharmacist | None:
    return get_pharmacist(ph_id)


def get_vacations_for_pharmacist_in_range(pharmacist_id: str, start: date, end: date) -> Vacation | None:
    docs = _query_all("vacation", [("pharmacist_id", "==", pharmacist_id)])
    for did, d in docs:
        v = Vacation.from_dict(did, d)
        if v.start_date and v.end_date:
            if v.start_date <= end and v.end_date >= start:
                return v
    return None


def batch_create_duties(duties_data: list[dict]):
    batch = get_db().batch()
    for d in duties_data:
        ref = _col("duty_schedule").document()
        batch.set(ref, d)
    batch.commit()


def delete_duties_for_month(year: int, month: int):
    duties = get_duties_for_month(year, month)
    if not duties:
        return
    batch = get_db().batch()
    for d in duties:
        ref = _col("duty_schedule").document(d.id)
        batch.delete(ref)
    batch.commit()


# --- USER ---

def get_user_by_id(doc_id: str) -> User | None:
    data = _get("user", doc_id)
    if data:
        return User.from_dict(doc_id, data)
    return None


def get_user_by_username(username: str) -> User | None:
    docs = _query_all("user", [("username", "==", username)])
    if docs:
        return User.from_dict(docs[0][0], docs[0][1])
    return None


def create_default_admin():
    existing = get_user_by_username("admin")
    if not existing:
        u = User(username="admin")
        u.set_password("admin123")
        _add("user", u.to_dict())
