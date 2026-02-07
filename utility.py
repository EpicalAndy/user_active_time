"""
Утилиты для форматирования и конвертации дат/времени
"""

import datetime

from config import (
    DATE_DISPLAY_FORMAT,
    DATE_KEY_FORMAT,
    TIME_FORMAT,
    TIMESTAMP_FORMAT,
)


def format_duration(seconds: int) -> str:
    """Форматирует секунды в читаемый вид: Xч Yм Zс"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}ч {minutes}м {secs}с"


def format_date_key(dt: datetime.datetime | datetime.date) -> str:
    """Форматирует дату в ключ состояния: YYYY-MM-DD"""
    return dt.strftime(DATE_KEY_FORMAT)


def format_time(dt: datetime.datetime) -> str:
    """Форматирует время: HH:MM:SS"""
    return dt.strftime(TIME_FORMAT)


def format_timestamp(dt: datetime.datetime) -> str:
    """Форматирует дату и время: YYYY-MM-DD HH:MM:SS"""
    return dt.strftime(TIMESTAMP_FORMAT)


def format_date_display(dt: datetime.date) -> str:
    """Форматирует дату для отображения: dd.mm.yyyy"""
    return dt.strftime(DATE_DISPLAY_FORMAT)


def parse_date_key(date_key: str) -> datetime.date:
    """Парсит ключ YYYY-MM-DD в datetime.date"""
    return datetime.datetime.strptime(date_key, DATE_KEY_FORMAT).date()


def parse_time(time_str: str) -> datetime.datetime:
    """Парсит строку HH:MM:SS в datetime"""
    return datetime.datetime.strptime(time_str, TIME_FORMAT)


def calculate_activity_percent(active_seconds: int, max_work_hours: int) -> float:
    """Вычисляет процент активности относительно максимального рабочего времени"""
    max_work_seconds = max_work_hours * 3600
    if max_work_seconds > 0:
        return (active_seconds / max_work_seconds) * 100
    return 0.0
