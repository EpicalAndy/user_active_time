"""
Тесты чтения дневного отчёта для окна просмотра (`modules/report_reader.py`).

Логика раньше жила внутри окна отчёта и без tkinter не проверялась.
Проверяется разбор файла обеих схем (v1 из событий лога, v2 из сырых
интервалов), парные значения «время (процент)» и раскладка интервалов графика.

Запуск: `python -m pytest tests/test_report_reader.py`
или как скрипт: `python tests/test_report_reader.py`.
"""

import datetime
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules.report_reader import (  # noqa: E402
    STATE_ACTIVE,
    STATE_INACTIVE,
    STATE_MANUAL,
    build_intervals,
    combine_time_percent,
    manual_hour_intervals,
    parse_report,
)

HOUR = 3600


def ts(hour, minute=0):
    return datetime.datetime(2026, 9, 14, hour, minute)


def write_report(data: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


# --- Парные значения ---


def test_combine_time_percent_uses_given_norm():
    # 6ч от нормы 7ч30м — процент от переданной нормы, не от рабочего времени.
    assert combine_time_percent(6 * HOUR, int(7.5 * HOUR)) == "6ч 0м 0с (80.0%)"


def test_combine_time_percent_without_norm_or_value():
    assert combine_time_percent(6 * HOUR, 0) == "6ч 0м 0с"
    assert combine_time_percent(0, 8 * HOUR) == "—"
    assert combine_time_percent(None, 8 * HOUR) == "—"


# --- Интервалы графика по событиям (схема v1) ---


def test_build_intervals_marks_active_idle_and_manual():
    events = [
        (ts(9), "MONITOR_START"),
        (ts(10), "INPUT_INACTIVE"),
        (ts(10, 30), "INPUT_ACTIVE"),
        (ts(11), "MANUAL_ADD_START"),
        (ts(12), "MANUAL_ADD_END"),
        (ts(13), "MONITOR_STOP"),
    ]
    assert build_intervals(events) == [
        (9.0, 10.0, STATE_ACTIVE),
        (10.0, 10.5, STATE_INACTIVE),
        (10.5, 11.0, STATE_ACTIVE),
        (11.0, 12.0, STATE_MANUAL),
        (12.0, 13.0, STATE_ACTIVE),
    ]


def test_build_intervals_sorts_events_added_out_of_order():
    # Ручная запись задним числом попадает в лог позже по строке, но раньше по времени.
    events = [(ts(12), "MONITOR_STOP"), (ts(9), "MONITOR_START")]
    assert build_intervals(events) == [(9.0, 12.0, STATE_ACTIVE)]


def test_build_intervals_empty():
    assert build_intervals([]) == []


def test_manual_hour_intervals_pairs_start_and_end():
    events = [
        (ts(9), "MONITOR_START"),
        (ts(11), "MANUAL_ADD_START"),
        (ts(12, 15), "MANUAL_ADD_END"),
        (ts(13), "MANUAL_ADD_END"),  # хвост без начала — игнорируется
    ]
    assert manual_hour_intervals(events) == [(11.0, 12.25)]


# --- Разбор файла ---


def test_parse_report_rejects_foreign_json():
    path = write_report({"foo": "bar"})
    try:
        assert parse_report(path) is None
    finally:
        os.remove(path)


def test_parse_report_v2_builds_segments_from_raw_intervals():
    path = write_report({
        "version": 2,
        "date": "2026-09-14",
        "username": "user",
        "active_seconds": 3 * HOUR,
        "total_work_seconds": 4 * HOUR,
        "max_work_seconds": 8 * HOUR,
        "break_seconds": 1800,
        "activity_norm_seconds": int(7.5 * HOUR),
        "session_count": 1,
        "first_login": "09:00:00",
        "last_logout": "13:00:00",
        "sessions": [{"start": "2026-09-14 09:00:00", "end": "2026-09-14 13:00:00"}],
        "idle": [{"from": "2026-09-14 10:00:00", "to": "2026-09-14 11:00:00"}],
        "log": [
            "2026-09-14 09:00:00 | user | MONITOR_START",
            "2026-09-14 11:30:00 | user | MANUAL_ADD_START",
            "2026-09-14 12:00:00 | user | MANUAL_ADD_END",
        ],
    })
    try:
        data = parse_report(path)
    finally:
        os.remove(path)

    assert data["date"] == "14.09.2026"
    assert data["day_bounds"] == "09:00:00 — 13:00:00"
    assert data["active_combined"] == "3ч 0м 0с (40.0%)"   # от нормы 7ч30м
    assert data["work_combined"] == "4ч 0м 0с (50.0%)"     # от 8ч
    assert data["break_time"] == "0ч 30м 0с"
    # Часовой гэп простоя минус текущий таймаут: простой начинается позже 10:00.
    timeout_h = config.INPUT_ACTIVITY_TIMEOUT / HOUR
    assert data["intervals"] == [
        (9.0, 10.0 + timeout_h, STATE_ACTIVE),
        (10.0 + timeout_h, 11.0, STATE_INACTIVE),
        (11.0, 13.0, STATE_ACTIVE),
    ]
    assert data["manual_intervals"] == [(11.5, 12.0)]


def test_parse_report_v1_falls_back_to_log_events():
    path = write_report({
        "date": "2026-09-14",
        "active_seconds": HOUR,
        "max_work_seconds": 8 * HOUR,
        "log": [
            "2026-09-14 09:00:00 | user | MONITOR_START",
            "2026-09-14 10:00:00 | user | MONITOR_STOP",
        ],
    })
    try:
        data = parse_report(path)
    finally:
        os.remove(path)
    assert data["intervals"] == [(9.0, 10.0, STATE_ACTIVE)]
    assert data["manual_intervals"] == []
    # Без перерыва в старом отчёте норма активности равна рабочему времени.
    assert data["activity_norm"] == "8ч 0м 0с"


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
