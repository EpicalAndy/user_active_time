"""
Сборка отчёта за произвольный период из дневных отчётов в LOG_DIR.

Источник данных — текстовые дневные отчёты (`{username}_dd.mm.yyyy.txt`).
Все метрики, включая норму (максимальное рабочее время), берутся из файла —
агрегатор не обращается к текущим настройкам. Это сохраняет историческую
консистентность: дневной и периодный отчёты показывают одинаковые цифры.
"""

import datetime
import os
import re
from collections.abc import Iterable

from config import LOG_DIR, USERNAME
from constants import ENCODING
from utility import format_date_display, get_work_hours

# «Xч Yм Zс» (целые или дробные)
_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*ч\s+(\d+(?:\.\d+)?)\s*м\s+(\d+(?:\.\d+)?)\s*с"
)
_ACTIVE_TIME_RE = re.compile(r"^Общее активное время:\s*(.+)$", re.MULTILINE)
_TOTAL_WORK_RE = re.compile(r"^Общее время работы:\s*(.+)$", re.MULTILINE)
_MAX_WORK_RE = re.compile(r"^Максимальное рабочее время:\s*(.+)$", re.MULTILINE)


def _parse_duration(text: str) -> int | None:
    """Парсит «Xч Yм Zс» в секунды. None если строка не распознана."""
    m = _DURATION_RE.search(text)
    if not m:
        return None
    h, mn, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
    return int(h * 3600 + mn * 60 + s)


def get_report_path(date: datetime.date) -> str:
    return os.path.join(LOG_DIR, f"{USERNAME}_{format_date_display(date)}.txt")


def daterange(start: datetime.date, end: datetime.date) -> Iterable[datetime.date]:
    """Итерирует от start до end включительно."""
    cur = start
    while cur <= end:
        yield cur
        cur += datetime.timedelta(days=1)


def _read_day_metrics(date: datetime.date) -> dict | None:
    """Возвращает метрики из дневного отчёта или None, если файла нет / не парсится."""
    path = get_report_path(date)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding=ENCODING) as f:
            text = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    active_match = _ACTIVE_TIME_RE.search(text)
    if not active_match:
        return None
    active_seconds = _parse_duration(active_match.group(1)) or 0

    total_match = _TOTAL_WORK_RE.search(text)
    total_work_seconds = _parse_duration(total_match.group(1)) if total_match else None
    if total_work_seconds is None:
        total_work_seconds = 0

    # Норма берётся из файла. Fallback на конфиг — для совместимости со старыми
    # отчётами, где этой строки могло не быть.
    max_match = _MAX_WORK_RE.search(text)
    max_work_seconds = _parse_duration(max_match.group(1)) if max_match else None
    if max_work_seconds is None:
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

    Норма для всего периода считается по всем календарным дням (даже без файла),
    т.к. описывает «сколько должно быть отработано по настройкам».
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
