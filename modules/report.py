"""
Модуль формирования отчёта об активности пользователя
"""

import datetime
import os

from constants import (
    ENCODING,
    METRIC_FIRST_LOGIN,
    METRIC_LAST_LOGOUT,
    REPORT_FIELD_ACTIVE_TIME,
    REPORT_FIELD_MAX_WORK,
    REPORT_FIELD_TOTAL_WORK,
    REPORT_FIELDS_SECTION_HEADER,
    REPORT_KEY_ACTIVE_TIME,
    REPORT_KEY_MAX_WORK,
    REPORT_KEY_TOTAL_WORK,
)
from utility import calculate_activity_percent, format_date_display, format_duration, get_work_hours, parse_time


def get_report_filename(username: str, date: datetime.date) -> str:
    """Возвращает имя файла отчёта: userName_dd.mm.yyyy.txt"""
    return f"{username}_{format_date_display(date)}.txt"


def generate_report(
    username: str,
    date: datetime.date,
    active_seconds: int,
    first_login: str | None,
    last_logout: str | None,
    session_count: int,
    log_entries: list[str],
) -> str:
    """Генерирует текст отчёта за день"""
    work_hours = get_work_hours(date)
    max_work_seconds = int(work_hours * 3600)

    # Общее время работы (первый логин - последний разлогин)
    if first_login and last_logout:
        total_work_seconds = int((parse_time(last_logout) - parse_time(first_login)).total_seconds())
        if total_work_seconds > 0:
            total_work_time = format_duration(total_work_seconds)
        else:
            total_work_time = "—"
    else:
        total_work_time = "—"

    activity_percent = calculate_activity_percent(active_seconds, work_hours)

    lines = [
        f"Пользователь: {username}",
        f"Дата: {format_date_display(date)}",
        "",
        REPORT_FIELDS_SECTION_HEADER,
        f"{REPORT_KEY_ACTIVE_TIME} = {REPORT_FIELD_ACTIVE_TIME}",
        f"{REPORT_KEY_TOTAL_WORK} = {REPORT_FIELD_TOTAL_WORK}",
        f"{REPORT_KEY_MAX_WORK} = {REPORT_FIELD_MAX_WORK}",
        "",
        f"{METRIC_FIRST_LOGIN}: {first_login or '—'}",
        f"{METRIC_LAST_LOGOUT}: {last_logout or '—'}",
        f"{REPORT_FIELD_ACTIVE_TIME}: {format_duration(active_seconds)}",
        f"{REPORT_FIELD_MAX_WORK}: {format_duration(max_work_seconds)}",
        f"{REPORT_FIELD_TOTAL_WORK}: {total_work_time}",
        f"Количество активных сессий: {session_count}",
        f"Процент активности: {activity_percent:.1f}%",
        "",
        "*" * 50,
        "",
        "Лог активности:",
    ]

    for entry in log_entries:
        lines.append(entry)

    return "\n".join(lines) + "\n"


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
    """Генерирует и записывает отчёт в файл"""
    report_text = generate_report(
        username=username,
        date=date,
        active_seconds=active_seconds,
        first_login=first_login,
        last_logout=last_logout,
        session_count=session_count,
        log_entries=log_entries,
    )

    filename = get_report_filename(username, date)
    filepath = os.path.join(log_dir, filename)

    with open(filepath, "w", encoding=ENCODING) as f:
        f.write(report_text)
