"""
Тесты недельной полосы активности (данные, без окна).

Проверяется разложение недели по клеткам: набор дат в обоих режимах и вид
каждой клетки. Главное свойство — источники разделены: сегодня приходит из
живых stats виджета, прошлые дни читаются из дневных отчётов, а «нет данных»,
«выходной» и «ещё не наступил» не смешиваются с «поработал плохо».

Запуск: `python -m pytest tests/test_week_activity.py`
или как скрипт: `python tests/test_week_activity.py`.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import work_calendar  # noqa: E402
from modules.week_activity import (  # noqa: E402
    KIND_DATA,
    KIND_DAY_OFF,
    KIND_FUTURE,
    KIND_NO_DATA,
    WEEK_MODE_CALENDAR,
    WEEK_MODE_ROLLING,
    build_week,
    week_dates,
)

# Среда 3 сентября 2025: неделя Пн 01.09 – Вс 07.09, из неё прожиты Пн–Ср.
WEDNESDAY = datetime.date(2025, 9, 3)

# Рабочий день 8ч с перерывом 30м: норма активности 7ч30м, присутствие 8ч.
DAY = {
    "active_seconds": 21600,          # 6ч   = 80% нормы активности
    "total_work_seconds": 28800,      # 8ч   = 100% присутствия
    "max_work_seconds": 28800,
    "activity_norm_seconds": 27000,
}

# Живые stats сегодняшнего дня — намеренно НЕ совпадают с отчётом за тот же
# день: так видно, что сегодняшняя клетка взята из stats, а не с диска.
TODAY_STATS = {
    "is_working_day": True,
    "active_seconds": 10800,          # 3ч = 40% нормы
    "activity_percent": 40.0,
    "full_day_seconds": 14400,        # 4ч = 50% присутствия
    "max_work_seconds": 28800,
}


def reports(*dates):
    """Читалка отчётов, у которой данные есть только за указанные даты."""
    known = set(dates)
    return lambda date: dict(DAY, date=date) if date in known else None


def build(mode=WEEK_MODE_CALENDAR, today=WEDNESDAY, stats=TODAY_STATS, read=None):
    """Раскладывает неделю при фиксированном расписании: Пн–Пт по 8ч, Сб/Вс — 0."""
    saved_hours = dict(config.WORK_HOURS_BY_DAY)
    saved_entry = work_calendar.get_entry
    config.WORK_HOURS_BY_DAY.update({
        "monday": 8, "tuesday": 8, "wednesday": 8, "thursday": 8, "friday": 8,
        "saturday": 0, "sunday": 0,
    })
    # Календарь-исключения — файл пользователя; тест не должен от него зависеть.
    work_calendar.get_entry = lambda _date: None
    try:
        return build_week(today, mode, stats, read or reports())
    finally:
        config.WORK_HOURS_BY_DAY.clear()
        config.WORK_HOURS_BY_DAY.update(saved_hours)
        work_calendar.get_entry = saved_entry


def kinds(week):
    return [cell["kind"] for cell in week]


def test_calendar_week_starts_on_monday():
    """Календарный режим: всегда Пн–Вс той недели, в которую попал день."""
    dates = week_dates(WEDNESDAY, WEEK_MODE_CALENDAR)
    assert len(dates) == 7
    assert dates[0] == datetime.date(2025, 9, 1)
    assert dates[-1] == datetime.date(2025, 9, 7)


def test_rolling_week_ends_today():
    """Скользящий режим: сегодня — крайний справа, слева шесть предыдущих дней."""
    dates = week_dates(WEDNESDAY, WEEK_MODE_ROLLING)
    assert dates[-1] == WEDNESDAY
    assert dates[0] == datetime.date(2025, 8, 28)


def test_unknown_mode_falls_back_to_calendar():
    """Опечатка в настройке не должна ронять полосу."""
    assert week_dates(WEDNESDAY, "нет такого") == week_dates(WEDNESDAY, WEEK_MODE_CALENDAR)


def test_future_days_are_empty():
    """Дни после сегодня ещё не наступили — клетка без данных и без цвета."""
    week = build()
    assert kinds(week)[3:] == [KIND_FUTURE] * 4
    assert week[3]["activity_percent"] is None


def test_today_comes_from_stats_not_from_report():
    """Сегодняшняя клетка берётся из живых stats: отчёт отстаёт от них на чекпоинт."""
    week = build(read=reports(WEDNESDAY))
    today = week[2]
    assert today["is_today"] and today["kind"] == KIND_DATA
    assert today["activity_percent"] == 40.0     # из stats, а не 80% из отчёта
    assert today["work_percent"] == 50.0
    assert today["active_seconds"] == 10800


def test_past_day_percents_come_from_report():
    """Прошлый день: активность — от нормы активности, присутствие — от рабочих часов."""
    week = build(read=reports(datetime.date(2025, 9, 1)))
    monday = week[0]
    assert monday["kind"] == KIND_DATA
    assert monday["activity_percent"] == 80.0
    assert monday["work_percent"] == 100.0


def test_past_day_without_report_is_no_data():
    """Рабочий день без отчёта — «нет данных», а не ноль процентов."""
    week = build()
    assert week[0]["kind"] == KIND_NO_DATA
    assert week[0]["activity_percent"] is None


def test_day_off_stays_day_off_even_with_data():
    """У выходного нормы нет: клетка нерабочая, но отработанное время видно."""
    saturday = datetime.date(2025, 9, 6)
    week = build(mode=WEEK_MODE_ROLLING, today=datetime.date(2025, 9, 8),
                 stats=None, read=reports(saturday))
    cell = next(c for c in week if c["date"] == saturday)
    assert cell["kind"] == KIND_DAY_OFF
    assert cell["active_seconds"] == DAY["active_seconds"]
    assert cell["activity_percent"] is None


def test_non_working_today_is_day_off():
    """В нерабочий день stats сворачивается до флага — сегодня остаётся выходным."""
    week = build(today=datetime.date(2025, 9, 6), stats={"is_working_day": False})
    today = week[5]
    assert today["is_today"] and today["kind"] == KIND_DAY_OFF


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
