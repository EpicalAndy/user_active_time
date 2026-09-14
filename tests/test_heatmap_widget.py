"""
Тесты раскладки мини-виджета «Тепловая карта» (данные, без окна).

Проверяется, какие даты и в каких клетках окажутся при каждом сочетании
настроек: неделя/месяц × календарный/скользящий. Главное свойство — столбцы
всегда соответствуют дням недели: в скользящем режиме строки всё равно по семь
дней, а заголовок сдвинут так, что сегодняшний день недели стоит справа.

Запуск: `python -m pytest tests/test_heatmap_widget.py`
или как скрипт: `python tests/test_heatmap_widget.py`.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widget.mini import registry  # noqa: E402
from modules.widget.mini.heatmap import (  # noqa: E402
    PERIOD_MONTH,
    PERIOD_WEEK,
    RANGE_CALENDAR,
    RANGE_ROLLING,
    column_weekdays,
    grid_rows,
    rolling_month_start,
    selected_period,
    selected_range,
)

# Понедельник 14 сентября 2026.
MONDAY = datetime.date(2026, 9, 14)


def days(rows):
    """Номера дней по строкам; None — пустое место."""
    return [[d.day if d else None for d in row] for row in rows]


# --- Неделя ---


def test_calendar_week_is_monday_to_sunday():
    rows = grid_rows(MONDAY, PERIOD_WEEK, RANGE_CALENDAR)
    assert days(rows) == [[14, 15, 16, 17, 18, 19, 20]]
    assert column_weekdays(MONDAY, RANGE_CALENDAR) == [0, 1, 2, 3, 4, 5, 6]


def test_rolling_week_ends_today():
    rows = grid_rows(MONDAY, PERIOD_WEEK, RANGE_ROLLING)
    assert days(rows) == [[8, 9, 10, 11, 12, 13, 14]]
    # Вт..Вс, потом Пн — сегодняшний день недели справа.
    assert column_weekdays(MONDAY, RANGE_ROLLING) == [1, 2, 3, 4, 5, 6, 0]


# --- Месяц ---


def test_calendar_month_hides_neighbour_months():
    rows = grid_rows(MONDAY, PERIOD_MONTH, RANGE_CALENDAR)
    assert days(rows) == [
        [None, 1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12, 13],
        [14, 15, 16, 17, 18, 19, 20],
        [21, 22, 23, 24, 25, 26, 27],
        [28, 29, 30, None, None, None, None],
    ]


def test_rolling_month_ends_today_and_pads_first_row():
    rows = grid_rows(MONDAY, PERIOD_MONTH, RANGE_ROLLING)
    assert rows[0][:4] == [None] * 4
    assert rows[0][4] == datetime.date(2026, 8, 15)
    assert rows[-1][-1] == MONDAY
    assert all(len(row) == 7 for row in rows)
    # Все даты подряд, без дыр: 15.08–14.09 — 31 день.
    dates = [d for row in rows for d in row if d]
    assert len(dates) == 31
    assert all((b - a).days == 1 for a, b in zip(dates, dates[1:]))


def test_columns_hold_the_same_weekday_in_rolling_month():
    """Скользящий режим: в каждом столбце один и тот же день недели, как в заголовке."""
    rows = grid_rows(MONDAY, PERIOD_MONTH, RANGE_ROLLING)
    header = column_weekdays(MONDAY, RANGE_ROLLING)
    for row in rows:
        for col, date in enumerate(row):
            if date is not None:
                assert date.weekday() == header[col]


def test_rolling_month_start_clamps_short_previous_month():
    assert rolling_month_start(MONDAY) == datetime.date(2026, 8, 15)
    # Февраль короче: 31.03 − месяц упирается в 28.02, поэтому весь март.
    assert rolling_month_start(datetime.date(2026, 3, 31)) == datetime.date(2026, 3, 1)
    # Смена года.
    assert rolling_month_start(datetime.date(2026, 1, 15)) == datetime.date(2025, 12, 16)


# --- Настройки ---


def test_broken_settings_fall_back_to_defaults():
    assert selected_period({}) == PERIOD_WEEK
    assert selected_range({}) == RANGE_CALENDAR
    assert selected_period({"period": "year"}) == PERIOD_WEEK
    assert selected_range({"range": 42}) == RANGE_CALENDAR
    assert selected_period({"period": "month"}) == PERIOD_MONTH
    assert selected_range({"range": "rolling"}) == RANGE_ROLLING


def test_registry_declares_both_options_as_choices():
    opts = registry.options_for("heatmap")
    assert [o["key"] for o in opts] == ["period", "range"]
    assert all(o.get("kind", registry.OPTION_CHOICE) == registry.OPTION_CHOICE for o in opts)
    assert registry.default_opts("heatmap") == {"period": PERIOD_WEEK, "range": RANGE_CALENDAR}


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
