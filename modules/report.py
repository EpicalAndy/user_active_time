"""
Модуль формирования дневного JSON-отчёта об активности пользователя.

Файл: {username}_dd.mm.yyyy.json. Имя сохранено для совместимости с тулбаром
«Папка с отчётами» — пользователю всё ещё видны привычные даты.

Схема — см. REPORT_JSON_VERSION в constants.py.
"""

import datetime
import os

from config import LOG_DIR, USERNAME
from constants import REPORT_JSON_EXT, REPORT_JSON_VERSION
from modules.json_file import read_json, write_json_atomic
from utility import format_date_display, parse_time


def get_report_path(date: datetime.date) -> str:
    """Путь к дневному отчёту: LOG_DIR/userName_dd.mm.yyyy.json"""
    return os.path.join(LOG_DIR, f"{USERNAME}_{format_date_display(date)}{REPORT_JSON_EXT}")


def load_report(date: datetime.date) -> dict | None:
    """Содержимое дневного отчёта или None, если файла нет или он битый."""
    data = read_json(get_report_path(date))
    return data if isinstance(data, dict) else None


def _compute_total_work_seconds(first_login: str | None, last_logout: str | None) -> int | None:
    """Длительность от первого входа до последнего выхода (None если данных нет)."""
    if not first_login or not last_logout:
        return None
    seconds = int((parse_time(last_logout) - parse_time(first_login)).total_seconds())
    return seconds if seconds > 0 else None


def build_report_data(
    username: str,
    date: datetime.date,
    active_seconds: int,
    max_work_seconds: int,
    first_login: str | None,
    last_logout: str | None,
    session_count: int,
    log_entries: list[str],
    sessions: list | None = None,
    idle: list | None = None,
    break_seconds: int = 0,
) -> dict:
    """Формирует словарь дневного отчёта согласно схеме."""
    return {
        "version": REPORT_JSON_VERSION,
        "username": username,
        "date": date.isoformat(),  # YYYY-MM-DD — машинный формат
        "first_login": first_login,
        "last_logout": last_logout,
        "active_seconds": active_seconds,
        "max_work_seconds": max_work_seconds,
        # Перерыв не входит в норму активности, но входит в присутствие:
        # max_work_seconds — сколько нужно быть на месте, activity_norm_seconds —
        # от чего считается 100% активности.
        "break_seconds": break_seconds,
        "activity_norm_seconds": max(0, max_work_seconds - break_seconds),
        "total_work_seconds": _compute_total_work_seconds(first_login, last_logout),
        "session_count": session_count,
        # Сырые интервалы (v2): источник истины для пересчёта active_seconds.
        "sessions": list(sessions or []),
        "idle": list(idle or []),
        "log": list(log_entries),
    }


def write_report(
    date: datetime.date,
    active_seconds: int,
    first_login: str | None,
    last_logout: str | None,
    session_count: int,
    log_entries: list[str],
    sessions: list | None = None,
    idle: list | None = None,
):
    """Записывает дневной JSON-отчёт. Норма и перерыв берутся из utility."""
    # Импорт внутри, чтобы избежать циклов и не тянуть config на верхний уровень.
    from utility import get_break_hours, get_work_hours
    max_work_seconds = int(get_work_hours(date) * 3600)
    break_seconds = int(get_break_hours(date) * 3600)

    data = build_report_data(
        username=USERNAME,
        date=date,
        active_seconds=active_seconds,
        max_work_seconds=max_work_seconds,
        first_login=first_login,
        last_logout=last_logout,
        session_count=session_count,
        log_entries=log_entries,
        sessions=sessions,
        idle=idle,
        break_seconds=break_seconds,
    )

    write_json_atomic(get_report_path(date), data)
