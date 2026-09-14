"""
Тесты строки «Таймлайн дня» в теле виджета (данные, без окна).

Проверяется то, что попадёт на полосу помимо самой ленты: отметки целых часов
(строго внутри отрезка, без дублирования краёв) и текст подсказки — границы
отрезка и активность в доле от рабочего времени, а не от нормы.

Запуск: `python -m pytest tests/test_day_timeline.py`
или как скрипт: `python tests/test_day_timeline.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import TIMELINE_TOOLTIP_NO_DATA  # noqa: E402
from modules.widget.day_timeline import (  # noqa: E402
    hour_tick_positions,
    tooltip_text,
)

HOUR = 3600
WIDTH = 180


def timeline(start, end):
    return {"start_seconds": start, "end_seconds": end, "segments": []}


# --- Отметки часов ---


def test_ticks_at_every_whole_hour_inside_span():
    # 09:30–12:30: внутри ровно три целых часа — 10, 11, 12.
    ticks = hour_tick_positions(timeline(9 * HOUR + 1800, 12 * HOUR + 1800), WIDTH)
    assert ticks == [WIDTH / 6, WIDTH / 2, WIDTH * 5 / 6]


def test_span_edges_on_whole_hour_are_not_ticks():
    # Логин ровно в 9:00, «сейчас» ровно 12:00 — края полосы отметками не дублируются.
    ticks = hour_tick_positions(timeline(9 * HOUR, 12 * HOUR), WIDTH)
    assert ticks == [WIDTH / 3, WIDTH * 2 / 3]


def test_short_span_without_whole_hour_has_no_ticks():
    assert hour_tick_positions(timeline(9 * HOUR + 60, 9 * HOUR + 1500), WIDTH) == []


def test_empty_span_has_no_ticks():
    assert hour_tick_positions(timeline(9 * HOUR, 9 * HOUR), WIDTH) == []


# --- Подсказка ---


def test_tooltip_shows_bounds_and_share_of_work_time():
    stats = {
        "timeline": timeline(8 * HOUR + 712, 15 * HOUR + 2400),
        "full_day_seconds": 7 * HOUR,
        "active_seconds": 6 * HOUR + 60,
        # Норма нарочно другая: подсказка считает долю от рабочего времени.
        "activity_norm_seconds": 8 * HOUR,
    }
    text = tooltip_text(stats)
    header, line = text.split("\n")
    assert header == "08:11 — 15:40"
    assert "6ч 1м" in line
    assert "85.9%" in line


def test_tooltip_before_first_login():
    assert tooltip_text({"timeline": None, "full_day_seconds": 0}) == TIMELINE_TOOLTIP_NO_DATA
    assert tooltip_text({}) == TIMELINE_TOOLTIP_NO_DATA


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
