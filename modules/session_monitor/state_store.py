"""
Хранилище состояния монитора: `state.json` и схема записи дня.

Самый нижний слой пакета — знает, как данные лежат, и ничего не знает о том,
кто их меняет. Здесь же формат записи дня (схема v2: `sessions`/`idle` как
источник истины) и сериализация интервалов.

`state.json` хранит только сегодняшний и будущие дни: прошедшие вычищаются
`cleanup_old_days` после записи отчёта, и durable-хранилищем для них становится
сам дневной отчёт (чтение — `day_report.load_report_day_state`).
"""

import datetime
import json
import os

from config import LOG_DIR, STATE_FILE
from constants import ENCODING
from utility import format_date_key, format_timestamp, parse_timestamp
from .journal import manual_seconds

os.makedirs(LOG_DIR, exist_ok=True)


def load_state() -> dict:
    """Загружает состояние из файла"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding=ENCODING) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(state: dict):
    """Сохраняет состояние в файл (атомарно через временный файл)"""
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w", encoding=ENCODING) as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, STATE_FILE)


def cleanup_old_days(session_start=None):
    """Удаляет из state.json данные за прошедшие дни после записи их отчётов.

    Не выполняет очистку, если текущая сессия началась до сегодня
    (кросс-полуночная сессия ещё не завершена) — вызывающая сторона передаёт
    её начало через `session_start` (владелец рантайма — session.py).
    """
    if session_start is not None and session_start.date() < datetime.date.today():
        return

    today = format_date_key(datetime.date.today())
    state = load_state()
    old_keys = [key for key in state if key < today]
    if not old_keys:
        return
    for key in old_keys:
        del state[key]
    save_state(state)
    print(f"[STATE] Удалены устаревшие данные за: {', '.join(sorted(old_keys))}")


# === Схема записи дня ===


def ensure_v2(day_state: dict):
    """Доводит запись дня до схемы v2 (sessions/idle/legacy_base_seconds).

    Для старой записи (v1) сохраняет уже накопленное active_seconds как
    legacy-смещение, вычитая ручное время, которое будет пересчитано из лога
    заново, — чтобы не задвоить его.
    """
    if "sessions" in day_state and "idle" in day_state:
        return
    existing_active = day_state.get("active_seconds", 0)
    day_state.setdefault("sessions", [])
    day_state.setdefault("idle", [])
    day_state["legacy_base_seconds"] = max(
        0, existing_active - manual_seconds(day_state.get("log_entries", [])),
    )


def fresh_day_state() -> dict:
    """Пустая запись дня (схема v2)."""
    return {
        "active_seconds": 0,
        "session_count": 0,
        "first_login": None,
        "last_logout": None,
        "sessions": [],
        "idle": [],
        "legacy_base_seconds": 0,
        "log_entries": [],
    }


def get_day_state(state: dict, date_key: str) -> dict:
    """Возвращает состояние дня, создавая если не существует (схема v2)."""
    if date_key not in state:
        state[date_key] = fresh_day_state()
    else:
        ensure_v2(state[date_key])
    return state[date_key]


def bump_last_logout(day_state: dict, candidate: str):
    """Устанавливает last_logout в максимум из существующего и candidate."""
    existing = day_state.get("last_logout")
    if existing is None or candidate > existing:
        day_state["last_logout"] = candidate


# === Интервалы дня (sessions / idle) ===


def parse_session_intervals(items: list) -> list:
    """Парсит [{"start","end"}] в список (datetime, datetime)."""
    out = []
    for it in items:
        try:
            out.append((parse_timestamp(it["start"]), parse_timestamp(it["end"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def parse_idle_intervals(items: list) -> list:
    """Парсит [{"from","to"}] в список (datetime, datetime)."""
    out = []
    for it in items:
        try:
            out.append((parse_timestamp(it["from"]), parse_timestamp(it["to"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def interval_item(interval, key_start: str, key_end: str) -> dict:
    """Сериализует (datetime, datetime) в {key_start, key_end} (TIMESTAMP-формат)."""
    start, end = interval
    return {key_start: format_timestamp(start), key_end: format_timestamp(end)}


def iter_dates(start_dt, end_dt):
    """Итерирует даты от start_dt.date() до end_dt.date() включительно."""
    day = start_dt.date()
    last = end_dt.date()
    while day <= last:
        yield day
        day += datetime.timedelta(days=1)


def add_interval_to_days(state: dict, start_dt, end_dt, list_key: str, item: dict):
    """Добавляет интервал в список list_key каждого дня, который он покрывает.

    Интервал кладётся целиком (без обрезки) в каждый затронутый день — пересечение
    с границами суток делает уже формула пересчёта, в т.ч. корректно для форы таймаута.
    """
    for day in iter_dates(start_dt, end_dt):
        get_day_state(state, format_date_key(day))[list_key].append(item)
