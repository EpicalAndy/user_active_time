"""
Сборка отчёта за произвольный период из дневных JSON-отчётов в LOG_DIR.

Источник данных — `{username}_dd.mm.yyyy.json`. Все метрики, включая норму,
читаются из файла; конфиг используется только как fallback, если в файле
поле отсутствует (например, повреждённый отчёт).
"""

import datetime
import json
import os
from collections.abc import Iterable

from config import LOG_DIR, USERNAME
from constants import ENCODING, REPORT_JSON_EXT
from utility import format_date_display, get_work_hours


def get_report_path(date: datetime.date) -> str:
    return os.path.join(LOG_DIR, f"{USERNAME}_{format_date_display(date)}{REPORT_JSON_EXT}")


def daterange(start: datetime.date, end: datetime.date) -> Iterable[datetime.date]:
    """Итерирует от start до end включительно."""
    cur = start
    while cur <= end:
        yield cur
        cur += datetime.timedelta(days=1)


def _read_day_metrics(date: datetime.date) -> dict | None:
    """Загружает дневной JSON и возвращает метрики или None, если файла нет / битый."""
    path = get_report_path(date)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding=ENCODING) as f:
            data = json.load(f)
    except (IOError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    active_seconds = data.get("active_seconds")
    if not isinstance(active_seconds, int):
        return None

    total_work_seconds = data.get("total_work_seconds") or 0
    if not isinstance(total_work_seconds, int):
        total_work_seconds = 0

    max_work_seconds = data.get("max_work_seconds")
    if not isinstance(max_work_seconds, int):
        max_work_seconds = int(get_work_hours(date) * 3600)

    return {
        "date": date,
        "active_seconds": active_seconds,
        "total_work_seconds": total_work_seconds,
        "max_work_seconds": max_work_seconds,
    }


def build_period_report(start: datetime.date, end: datetime.date) -> dict:
    """Собирает отчёт за период.

    Возвращает:
        {"missing_boundary": [date, ...]}  — если отсутствует одна или обе крайние даты
        {"days": [...], "totals": {...}}   — успешно собранные данные
    """
    missing_boundary = [d for d in (start, end) if _read_day_metrics(d) is None]
    if missing_boundary:
        return {"missing_boundary": missing_boundary}

    days = []
    for d in daterange(start, end):
        m = _read_day_metrics(d)
        if m is not None:
            days.append(m)

    totals = {
        "active_seconds": sum(d["active_seconds"] for d in days),
        "total_work_seconds": sum(d["total_work_seconds"] for d in days),
        "max_work_seconds": sum(d["max_work_seconds"] for d in days),
    }

    return {"days": days, "totals": totals, "missing_boundary": []}


def percent(part: int, whole: int) -> float | None:
    """Безопасный процент: None если whole == 0."""
    if whole <= 0:
        return None
    return part / whole * 100
