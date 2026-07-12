from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash


@dataclass
class Daira:
    id: str = ""
    name_ar: str = ""
    name_fr: str = ""

    def to_dict(self):
        return {"id": self.id, "name_ar": self.name_ar, "name_fr": self.name_fr}

    @classmethod
    def from_dict(cls, doc_id: str, data: dict):
        return cls(id=doc_id, name_ar=data.get("name_ar", ""), name_fr=data.get("name_fr", ""))


@dataclass
class Municipality:
    id: str = ""
    name_ar: str = ""
    name_fr: str = ""
    daira_id: str = ""

    def to_dict(self):
        return {"id": self.id, "name_ar": self.name_ar, "name_fr": self.name_fr, "daira_id": self.daira_id}

    @classmethod
    def from_dict(cls, doc_id: str, data: dict):
        return cls(
            id=doc_id,
            name_ar=data.get("name_ar", ""),
            name_fr=data.get("name_fr", ""),
            daira_id=str(data.get("daira_id", "")),
        )


@dataclass
class Pharmacist:
    id: str = ""
    name_fr: str = ""
    address_fr: str = ""
    municipality_id: str = ""
    license_number: str = ""
    rotation_order: int = 0
    is_active: bool = True

    def to_dict(self):
        return {
            "id": self.id,
            "name_fr": self.name_fr,
            "address_fr": self.address_fr,
            "municipality_id": self.municipality_id,
            "license_number": self.license_number,
            "rotation_order": self.rotation_order,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, doc_id: str, data: dict):
        return cls(
            id=doc_id,
            name_fr=data.get("name_fr", ""),
            address_fr=data.get("address_fr", ""),
            municipality_id=str(data.get("municipality_id", "")),
            license_number=data.get("license_number", ""),
            rotation_order=int(data.get("rotation_order", 0)),
            is_active=bool(data.get("is_active", True)),
        )


@dataclass
class Vacation:
    id: str = ""
    pharmacist_id: str = ""
    start_date: date = None
    end_date: date = None

    def to_dict(self):
        return {
            "id": self.id,
            "pharmacist_id": self.pharmacist_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }

    @classmethod
    def from_dict(cls, doc_id: str, data: dict):
        start = data.get("start_date")
        end = data.get("end_date")
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        return cls(
            id=doc_id,
            pharmacist_id=str(data.get("pharmacist_id", "")),
            start_date=start,
            end_date=end,
        )


@dataclass
class DutySchedule:
    id: str = ""
    date: date = None
    pharmacist_id: str = ""
    municipality_id: str = ""
    shift_type: str = "NIGHT"
    is_holiday: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "pharmacist_id": self.pharmacist_id,
            "municipality_id": self.municipality_id,
            "shift_type": self.shift_type,
            "is_holiday": self.is_holiday,
        }

    @classmethod
    def from_dict(cls, doc_id: str, data: dict):
        d = data.get("date")
        if isinstance(d, str):
            d = date.fromisoformat(d)
        return cls(
            id=doc_id,
            date=d,
            pharmacist_id=str(data.get("pharmacist_id", "")),
            municipality_id=str(data.get("municipality_id", "")),
            shift_type=data.get("shift_type", "NIGHT"),
            is_holiday=bool(data.get("is_holiday", False)),
        )


@dataclass
class User:
    id: str = ""
    username: str = ""
    password_hash: str = ""

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active_user(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    def to_dict(self):
        return {"id": self.id, "username": self.username, "password_hash": self.password_hash}

    @classmethod
    def from_dict(cls, doc_id: str, data: dict):
        return cls(id=doc_id, username=data.get("username", ""), password_hash=data.get("password_hash", ""))
