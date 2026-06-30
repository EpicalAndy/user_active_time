"""
Тесты чистого ядра вычисления активного времени (modules/activity_intervals.py).

Запуск: `python -m pytest tests/test_activity_intervals.py`
или как скрипт: `python tests/test_activity_intervals.py`.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import activity_intervals as ai  # noqa: E402

DAY = datetime.date(2026, 6, 21)
NEXT = datetime.date(2026, 6, 22)


def dt(h, m=0, s=0, day=DAY):
    return datetime.datetime(day.year, day.month, day.day, h, m, s)


def test_session_no_idle():
    sessions = [(dt(9), dt(17))]
    assert ai.compute_active_seconds(sessions, [], 300, DAY) == 8 * 3600


def test_idle_shorter_than_timeout_ignored():
    sessions = [(dt(9), dt(17))]
    idle = [(dt(10), dt(10, 3))]  # 180с < 300
    assert ai.compute_active_seconds(sessions, idle, 300, DAY) == 8 * 3600


def test_idle_longer_than_timeout_subtracts_excess():
    sessions = [(dt(9), dt(17))]
    idle = [(dt(10), dt(10, 30))]  # 1800с
    # inactive = 1800 - 300 = 1500
    assert ai.compute_active_seconds(sessions, idle, 300, DAY) == 8 * 3600 - 1500


def test_recompute_with_different_timeout():
    """Тот же гэп при разном таймауте → разное активное (пересчёт истории)."""
    sessions = [(dt(9), dt(17))]
    idle = [(dt(10), dt(10, 30))]  # 1800с
    assert ai.compute_active_seconds(sessions, idle, 600, DAY) == 8 * 3600 - 1200
    assert ai.compute_active_seconds(sessions, idle, 1800, DAY) == 8 * 3600  # фора = длине
    assert ai.compute_active_seconds(sessions, idle, 3600, DAY) == 8 * 3600  # фора > длины


def test_cross_midnight_session_split_by_overlap():
    sessions = [(dt(23), dt(1, 0, 0, day=NEXT))]
    assert ai.compute_active_seconds(sessions, [], 300, DAY) == 3600
    assert ai.compute_active_seconds(sessions, [], 300, NEXT) == 3600


def test_cross_midnight_idle_grace_applied_once():
    """Фора таймаута применяется один раз ко всему гэпу, не на каждый день."""
    sessions = [(dt(22), dt(2, 0, 0, day=NEXT))]
    idle = [(dt(23, 50), dt(0, 30, 0, day=NEXT))]  # 2400с, inactive = [23:55, 00:30]
    # День 21: сессия 22:00–24:00 = 7200; inactive 23:55–24:00 = 300
    assert ai.compute_active_seconds(sessions, idle, 300, DAY) == 7200 - 300
    # День 22: сессия 00:00–02:00 = 7200; inactive 00:00–00:30 = 1800
    assert ai.compute_active_seconds(sessions, idle, 300, NEXT) == 7200 - 1800


def test_empty_inputs():
    assert ai.compute_active_seconds([], [], 300, DAY) == 0


def test_inactive_seconds_helper():
    idle = [(dt(10), dt(10, 30)), (dt(11), dt(11, 2))]  # 1800-300, 120<300→0
    assert ai.inactive_seconds(idle, 300) == 1500


def test_day_segments_active_inactive():
    sessions = [(dt(9), dt(12))]
    idle = [(dt(10), dt(11))]  # 3600с, inactive = [10:05, 11:00]
    segs = ai.day_segments(sessions, idle, 300, DAY)
    assert segs == [
        (dt(9), dt(10, 5), "active"),
        (dt(10, 5), dt(11), "inactive"),
        (dt(11), dt(12), "active"),
    ]
    # Сумма активных отрезков == compute_active_seconds
    active_total = sum((e - s).total_seconds() for s, e, st in segs if st == "active")
    assert int(active_total) == ai.compute_active_seconds(sessions, idle, 300, DAY)


def test_day_segments_short_idle_not_cut():
    sessions = [(dt(9), dt(12))]
    idle = [(dt(10), dt(10, 3))]  # короче таймаута → не режет
    segs = ai.day_segments(sessions, idle, 300, DAY)
    assert segs == [(dt(9), dt(12), "active")]


def test_day_segments_gap_between_sessions_is_inactive():
    # Экран блокируется между сессиями (LOCK→UNLOCK): пробел = простой, не пустота.
    sessions = [(dt(9), dt(10)), (dt(11), dt(12))]
    segs = ai.day_segments(sessions, [], 300, DAY)
    assert segs == [
        (dt(9), dt(10), "active"),
        (dt(10), dt(11), "inactive"),
        (dt(11), dt(12), "active"),
    ]


def test_day_segments_overlapping_sessions_no_negative_gap():
    sessions = [(dt(9), dt(11)), (dt(10), dt(12))]  # перекрытие
    segs = ai.day_segments(sessions, [], 300, DAY)
    assert segs == [
        (dt(9), dt(11), "active"),
        (dt(10), dt(12), "active"),
    ]


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
