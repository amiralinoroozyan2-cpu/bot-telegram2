import json
import threading
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_FILE = "data.json"
_lock = threading.Lock()

DEFAULT_DATA = {
    "users": {},
    "listings": {}
}


def _load() -> dict:
    if not os.path.exists(DATA_FILE):
        return dict(DEFAULT_DATA)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading data: {e}")
        return dict(DEFAULT_DATA)


def _save(data: dict):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Error saving data: {e}")


# ─── Users ────────────────────────────────────────────────────────────────────

def get_user(user_id: int) -> dict | None:
    with _lock:
        data = _load()
        return data["users"].get(str(user_id))


def upsert_user(user_id: int, username: str | None, first_name: str):
    with _lock:
        data = _load()
        uid = str(user_id)
        if uid not in data["users"]:
            data["users"][uid] = {
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.utcnow().isoformat(),
                "warned": False,
                "banned": False,
            }
        else:
            data["users"][uid]["username"] = username
            data["users"][uid]["first_name"] = first_name
        _save(data)


def mark_warned(user_id: int):
    with _lock:
        data = _load()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["warned"] = True
        _save(data)


def is_warned(user_id: int) -> bool:
    user = get_user(user_id)
    return user.get("warned", False) if user else False


def ban_user(user_id: int):
    with _lock:
        data = _load()
        uid = str(user_id)
        if uid not in data["users"]:
            data["users"][uid] = {
                "id": user_id,
                "username": None,
                "first_name": "",
                "joined_at": datetime.utcnow().isoformat(),
                "warned": False,
                "banned": True,
            }
        else:
            data["users"][uid]["banned"] = True
        _save(data)


def unban_user(user_id: int):
    with _lock:
        data = _load()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["banned"] = False
        _save(data)


def is_banned(user_id: int) -> bool:
    user = get_user(user_id)
    return user.get("banned", False) if user else False


def get_all_users() -> list[dict]:
    with _lock:
        data = _load()
        return list(data["users"].values())


# ─── Listings ─────────────────────────────────────────────────────────────────

def save_listing(code: str, listing: dict):
    with _lock:
        data = _load()
        data["listings"][code] = listing
        _save(data)


def get_listing(code: str) -> dict | None:
    with _lock:
        data = _load()
        return data["listings"].get(code.upper())


def update_listing(code: str, updates: dict):
    with _lock:
        data = _load()
        if code.upper() in data["listings"]:
            data["listings"][code.upper()].update(updates)
            _save(data)


def get_user_listings(user_id: int) -> list[dict]:
    with _lock:
        data = _load()
        return [
            l for l in data["listings"].values()
            if l.get("seller_id") == user_id
        ]


def get_all_listings() -> list[dict]:
    with _lock:
        data = _load()
        return list(data["listings"].values())
