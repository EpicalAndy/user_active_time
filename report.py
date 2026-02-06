"""
Модуль формирования отчёта об активности пользователя
"""

import datetime
import os

from config import MAX_WORK_HOURS


def format_duration(seconds: int) -> str:
    """Форматирует секунды в читаемый вид"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}ч {minutes}м {secs}с"


def get_report_filename(username: str, date: datetime.date) -> str:
    """Возвращает имя файла отчёта: userName_dd.mm.yyyy.txt"""
    date_str = date.strftime("%d.%m.%Y")
    return f"{username}_{date_str}.txt"


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
    max_work_seconds = MAX_WORK_HOURS * 3600
    date_str = date.strftime("%d.%m.%Y")

    # Общее время работы (первый логин - последний разлогин)
    if first_login and last_logout:
        first = datetime.datetime.strptime(first_login, "%H:%M:%S")
        last = datetime.datetime.strptime(last_logout, "%H:%M:%S")
        total_work_seconds = int((last - first).total_seconds())
        if total_work_seconds > 0:
            total_work_time = format_duration(total_work_seconds)
        else:
            total_work_time = "—"
    else:
        total_work_time = "—"

    # Процент активности (100% = максимальное рабочее время)
    if max_work_seconds > 0:
        activity_percent = (active_seconds / max_work_seconds) * 100
    else:
        activity_percent = 0.0

    lines = [
        f"Пользователь: {username}",
        f"Дата: {date_str}",
        "",
        f"Общее активное время: {format_duration(active_seconds)}",
        f"Максимальное рабочее время: {format_duration(max_work_seconds)}",
        f"Общее время работы: {total_work_time}",
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

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)
