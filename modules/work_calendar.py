"""
Календарь-исключения рабочего расписания.

Хранит привязанные к конкретным датам переопределения дневного лимита и
заметки. Единая точка вычисления нормы остаётся в utility.get_work_hours();
этот модуль лишь предоставляет переопределения поверх расписания по дням
недели (WORK_HOURS_BY_DAY).

Формат файла ~/active_time/work_calendar.json:
    { "YYYY-MM-DD": {"hours": <float|null>, "note": <str>}, ... }

Семантика поля hours:
    ключа нет ИЛИ hours == null → переопределения нет, действует расписание
    hours == 0                  → выходной (день не отслеживается)
    hours > 0                   → переопределённый дневной лимит в часах

Чтобы не плодить циклический импорт, модуль зависит только от config —
форматирование ключа-даты делается напрямую через DATE_KEY_FORMAT.
"""

import datetime
import json
import os

from config import CALENDAR_FILE, DATE_KEY_FORMAT
from constants import ENCODING

# Кэш в памяти: ключ-дата (YYYY-MM-DD) → {"hours": float|None, "note": str}.
# None означает «ещё не загружено» и отличается от пустого календаря ({}).
_cache: dict | None = None


def _date_key(date: datetime.date) -> str:
    return date.strftime(DATE_KEY_FORMAT)


def _ensure_loaded() -> dict:
    """Лениво загружает календарь в кэш и возвращает его."""
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def _load() -> dict:
    """Читает календарь из файла. При отсутствии/повреждении — пустой словарь."""
    if os.path.exists(CALENDAR_FILE):
        try:
            with open(CALENDAR_FILE, "r", encoding=ENCODING) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save():
    """Атомарно сохраняет кэш в файл (через временный файл + replace)."""
    data = _ensure_loaded()
    tmp_path = CALENDAR_FILE + ".tmp"
    with open(tmp_path, "w", encoding=ENCODING) as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, CALENDAR_FILE)


def reload():
    """Сбрасывает кэш — следующее чтение перечитает файл с диска."""
    global _cache
    _cache = None


def get_entry(date: datetime.date) -> dict | None:
    """Возвращает запись календаря для даты или None, если её нет."""
    entry = _ensure_loaded().get(_date_key(date))
    return entry if isinstance(entry, dict) else None


def get_override_hours(date: datetime.date) -> float | None:
    """
    Возвращает переопределённый дневной лимит для даты.

    None  — переопределения нет (действует расписание по дню недели).
    0.0   — день помечен выходным.
    >0    — переопределённый лимит в часах.
    """
    entry = get_entry(date)
    if entry is None:
        return None
    hours = entry.get("hours")
    if hours is None:
        return None
    try:
        return float(hours)
    except (TypeError, ValueError):
        return None


def get_note(date: datetime.date) -> str:
    """Возвращает заметку на дату (пустую строку, если её нет)."""
    entry = get_entry(date)
    if entry is None:
        return ""
    note = entry.get("note", "")
    return note if isinstance(note, str) else ""


def set_entry(date: datetime.date, hours: float | None, note: str = ""):
    """
    Создаёт/обновляет запись на дату и сохраняет файл.

    hours=None при пустой заметке означает «нет данных» — запись удаляется,
    чтобы файл не копил пустые ключи.
    """
    cache = _ensure_loaded()
    key = _date_key(date)
    note = (note or "").strip()
    if hours is None and not note:
        cache.pop(key, None)
    else:
        cache[key] = {"hours": hours, "note": note}
    _save()


def clear_entry(date: datetime.date):
    """Удаляет запись на дату (возврат к расписанию по дню недели) и сохраняет."""
    cache = _ensure_loaded()
    if cache.pop(_date_key(date), None) is not None:
        _save()
