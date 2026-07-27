"""
Мост между записью дня и дневным JSON-отчётом.

Две стороны одной пары: запись `day_state` в отчёт и восстановление `day_state`
из отчёта. Второе нужно потому, что `state.json` хранит только сегодняшний и
будущие дни — для прошедших дней источником истины служит сам отчёт
(см. `state_store.cleanup_old_days`).
"""

import json
import os

from config import LOG_DIR, USERNAME
from constants import ENCODING
from modules.report import get_report_filename, write_report
from utility import parse_date_key
from .activity import recompute_active
from .state_store import fresh_day_state


def update_report(date_key: str, day_state: dict, live_idle=None):
    """Обновляет файл отчёта для указанного дня.

    Открытая сессия (`open_session`, сохранена в state.json для устойчивости к
    сбоям) подмешивается в записываемые `sessions`, чтобы график/активность
    отражали идущую сессию. live_idle — открытый гэп простоя: пишется в файл,
    но НЕ хранится в state.json (транзиентный, при пересчёте не нужен).
    """
    sessions = list(day_state.get("sessions", []))
    if day_state.get("open_session"):
        sessions.append(day_state["open_session"])
    idle = list(day_state.get("idle", []))
    if live_idle:
        idle += live_idle
    write_report(
        log_dir=LOG_DIR,
        username=USERNAME,
        date=parse_date_key(date_key),
        active_seconds=day_state["active_seconds"],
        first_login=day_state["first_login"],
        last_logout=day_state["last_logout"],
        session_count=day_state["session_count"],
        log_entries=day_state["log_entries"],
        sessions=sessions,
        idle=idle,
    )


def load_report_day_state(date_key: str) -> dict | None:
    """Восстанавливает day_state из дневного отчёта (durable-хранилище прошлых дней).

    Для ручного редактирования прошедших дней источником истины служит их
    JSON-отчёт. Возвращает None, если отчёта нет/он повреждён.

    legacy_base_seconds подбирается так, чтобы recompute_active давал ровно
    сохранённое active_seconds (проекция сессий может отличаться, если с момента
    записи менялся INPUT_ACTIVITY_TIMEOUT, — «замораживаем» активное время дня).
    """
    path = os.path.join(LOG_DIR, get_report_filename(USERNAME, parse_date_key(date_key)))
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding=ENCODING) as f:
            data = json.load(f)
    except (IOError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    day_state = fresh_day_state()
    day_state["active_seconds"] = int(data.get("active_seconds") or 0)
    day_state["session_count"] = int(data.get("session_count") or 0)
    day_state["first_login"] = data.get("first_login")
    day_state["last_logout"] = data.get("last_logout")
    day_state["sessions"] = list(data.get("sessions") or [])
    day_state["idle"] = list(data.get("idle") or [])
    day_state["log_entries"] = list(data.get("log") or [])

    # legacy = сохранённое active − (проекция сессий/idle + ручное время).
    projection_plus_manual = recompute_active(day_state, parse_date_key(date_key))
    day_state["legacy_base_seconds"] = max(0, day_state["active_seconds"] - projection_plus_manual)
    return day_state
