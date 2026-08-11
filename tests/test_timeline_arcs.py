"""
Тесты раскладки круговой диаграммы «Таймлайн дня» (`timeline.arcs`).

Проверяется, что попадёт на канву: цветные дуги поверх красного фона-простоя.
Главное здесь — ни одна дуга не должна быть короче ячейки кольца: вырожденную
дугу Tk рисует как ПОЛНЫЙ круг, и одна секунда активности закрашивала зелёным
весь таймлайн (простой пропадал с диаграммы целиком).

Запуск: `python -m pytest tests/test_timeline_arcs.py`
или как скрипт: `python tests/test_timeline_arcs.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import theme  # noqa: E402
from modules.widget.mini.ring import MIN_ARC_DEGREES  # noqa: E402
from modules.widget.mini.timeline import arcs  # noqa: E402

HOUR = 3600


def timeline(*segments, start=9 * HOUR, end=18 * HOUR):
    return {"start_seconds": start, "end_seconds": end, "segments": list(segments)}


def total_extent(arc_list):
    """Сколько градусов круга закрашено дугами (extent отрицательный)."""
    return sum(-extent for _start, extent, _color in arc_list)


def colors(arc_list):
    return {color for _start, _extent, color in arc_list}


# --- Вырожденные дуги: та самая пропажа красного ---


def test_second_long_activity_does_not_paint_whole_ring():
    """8 секунд активности не должны закрасить круг: это был баг с пропажей простоя.

    Прежний код рисовал такую активность дугой в 0.089° — Tk чертил её полным
    кругом, и весь таймлайн становился зелёным до конца дня.
    """
    drawn = arcs(timeline((9 * HOUR, 9 * HOUR + 8, "active")))
    assert total_extent(drawn) < 360
    assert all(-extent >= MIN_ARC_DEGREES for _start, extent, _color in drawn)


def test_no_arc_is_shorter_than_a_cell():
    """Дуга короче ячейки вырождается в точку — Tk рисует её полным кругом."""
    day = timeline(
        (9 * HOUR, 9 * HOUR + 3, "active"),
        (10 * HOUR, 10 * HOUR + 30, "active"),
        (11 * HOUR, 12 * HOUR, "active"),
    )
    for _start, extent, _color in arcs(day):
        assert -extent >= MIN_ARC_DEGREES


def test_short_activity_next_to_long_one_is_absorbed_not_lost():
    """Секунды рядом с длинной активностью не теряются — они в той же дуге."""
    day = timeline((10 * HOUR, 11 * HOUR, "active"), (11 * HOUR, 11 * HOUR + 5, "active"))
    assert len(arcs(day)) == 1


# --- Простой остаётся виден ---


def test_idle_gap_leaves_red_on_the_ring():
    """Обеденный перерыв — это НЕ закрашенная часть круга (фон красный)."""
    day = timeline(
        (9 * HOUR, 13 * HOUR, "active"),
        (13 * HOUR, 14 * HOUR, "inactive"),
        (14 * HOUR, 18 * HOUR, "active"),
    )
    # Час из девяти — 40° круга; квантование по ячейкам даёт погрешность в ячейку.
    assert 40 - MIN_ARC_DEGREES <= 360 - total_extent(arcs(day)) <= 40 + MIN_ARC_DEGREES


def test_idle_is_never_drawn_itself():
    """Простой рисуется фоном круга, отдельной дугой его быть не должно."""
    day = timeline((9 * HOUR, 18 * HOUR, "inactive"))
    assert arcs(day) == []


def test_pure_activity_fills_the_ring():
    day = timeline((9 * HOUR, 18 * HOUR, "active"))
    assert round(total_extent(arcs(day))) == 360
    assert colors(arcs(day)) == {theme.COLOR_GREEN}


# --- Ручное время ---


def test_manual_time_is_drawn_blue():
    day = timeline(
        (9 * HOUR, 12 * HOUR, "active"),
        (12 * HOUR, 15 * HOUR, "manual"),
    )
    assert colors(arcs(day)) == {theme.COLOR_GREEN, theme.COLOR_BLUE}


def test_manual_wins_the_cell_over_equal_activity():
    """Пополам в одной ячейке — ручное время приоритетнее: его добавили руками."""
    day = timeline(
        (9 * HOUR, 9 * HOUR + 60, "active"),
        (9 * HOUR + 60, 9 * HOUR + 120, "manual"),
        start=9 * HOUR, end=18 * HOUR,
    )
    assert colors(arcs(day)) == {theme.COLOR_BLUE}


# --- Границы ---


def test_empty_span_gives_nothing():
    assert arcs(timeline(start=9 * HOUR, end=9 * HOUR)) == []


def test_segments_outside_span_are_clipped():
    """Отрезок за границами круга не должен уезжать за его пределы."""
    day = timeline((6 * HOUR, 21 * HOUR, "active"))
    assert round(total_extent(arcs(day))) == 360
    assert all(-360 <= start <= 360 for start, _extent, _color in arcs(day))


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
