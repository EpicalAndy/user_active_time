"""
Модуль формирования дневного JSON-отчёта об активности пользователя.

Файл: {username}_dd.mm.yyyy.json. Имя сохранено для совместимости с тулбаром
«Папка с отчётами» — пользователю всё ещё видны привычные даты.

Схема — см. REPORT_JSON_VERSION в constants.py.
"""

import datetime
import json
import os

from constants import ENCODING, REPORT_JSON_EXT, REPORT_JSON_VERSION
from utility import format_date_display, parse_time


def get_report_filename(username: str, date: datetime.date) -> str:
    """Возвращает имя файла отчёта: userName_dd.mm.yyyy.json"""
    return f"{username}_{format_date_display(date)}{REPORT_JSON_EXT}"


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
        "total_work_seconds": _compute_total_work_seconds(first_login, last_logout),
        "session_count": session_count,
        "log": list(log_entries),
    }


def write_report(
    log_dir: str,
    username: str,
    date: datetime.date,
    active_seconds: int,
    first_login: str | None,
    last_logout: str | None,
    session_count: int,
    log_entries: list[str],
):
    """Записывает дневной JSON-отчёт. Норма берётся из get_work_hours."""
    # Импорт внутри, чтобы избежать циклов и не тянуть config на верхний уровень.
    from utility import get_work_hours
    max_work_seconds = int(get_work_hours(date) * 3600)

    data = build_report_data(
        username=username,
        date=date,
        active_seconds=active_seconds,
        max_work_seconds=max_work_seconds,
        first_login=first_login,
        last_logout=last_logout,
        session_count=session_count,
        log_entries=log_entries,
    )

    filepath = os.path.join(log_dir, get_report_filename(username, date))
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding=ENCODING) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, filepath)
