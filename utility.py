"""
Утилиты для форматирования и конвертации дат/времени
"""

import datetime
import os
import sys

import config
from modules import work_calendar
from config import (
    DATE_DISPLAY_FORMAT,
    DATE_KEY_FORMAT,
    DEFAULT_WORK_HOURS,
    TIME_FORMAT,
    TIMESTAMP_FORMAT,
    WORK_HOURS_BY_DAY,
)


def resource_path(relative: str) -> str:
    """Абсолютный путь к ресурсу, поставляемому с приложением.

    В собранной сборке (PyInstaller) данные лежат рядом с исполняемым файлом —
    путь берётся от sys._MEIPASS. В обычном запуске — от корня проекта
    (на два уровня выше этого файла: utility.py → корень).
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


def format_duration(seconds: int) -> str:
    """Форматирует секунды в читаемый вид: Xч Yм Zс"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}ч {minutes}м {secs}с"


def format_duration_short(seconds: int) -> str:
    """Форматирует секунды в краткий вид без секунд: Xч Yм"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}ч {minutes}м"


def format_duration_signed(seconds: int) -> str:
    """То же, но со знаком: «1ч 20м», «-15м» для отрицательных значений.

    Нужна метрикам-остаткам, которые могут уйти в минус (свободное время).
    На отрицательных `format_duration_short` врёт из-за floor-деления:
    -900 дало бы «-1ч 45м» вместо «-15м».
    """
    if seconds < 0:
        return f"-{format_duration_short(-seconds)}"
    return format_duration_short(seconds)


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


def parse_timestamp(ts_str: str) -> datetime.datetime:
    """Парсит строку YYYY-MM-DD HH:MM:SS в datetime"""
    return datetime.datetime.strptime(ts_str, TIMESTAMP_FORMAT)


_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def get_work_hours(date: datetime.date) -> float:
    """Возвращает рабочие часы для указанного дня (0 = не отслеживать).

    Приоритет: переопределение из календаря-исключений (привязка к дате) →
    расписание по дню недели → DEFAULT_WORK_HOURS.
    """
    override = work_calendar.get_override_hours(date)
    if override is not None:
        return override
    day_name = _DAY_NAMES[date.weekday()]
    hours = WORK_HOURS_BY_DAY.get(day_name)
    if hours is None:
        return DEFAULT_WORK_HOURS
    return hours


def get_break_hours(date: datetime.date) -> float:
    """Возвращает перерыв за день в часах — часть рабочего времени вне нормы активности.

    Для нерабочего дня — 0: вычитать не из чего. Значение читается динамически
    (`config.BREAK_MINUTES`) — см. конвенцию hot-reload в шапке config.py.
    """
    if get_work_hours(date) == 0:
        return 0.0
    return max(0.0, config.BREAK_MINUTES / 60)


def get_activity_norm_hours(date: datetime.date) -> float:
    """Возвращает норму активности (100%) в часах: рабочие часы минус перерыв.

    Отличается от get_work_hours: та задаёт, сколько нужно *присутствовать*
    (общее рабочее время), а эта — от чего считается процент активности.
    """
    return max(0.0, get_work_hours(date) - get_break_hours(date))


def calculate_activity_percent(active_seconds: int, norm_hours: float) -> float:
    """Вычисляет процент активности относительно нормы активности (см. get_activity_norm_hours)"""
    norm_seconds = norm_hours * 3600
    if norm_seconds > 0:
        return (active_seconds / norm_seconds) * 100
    return 0.0
