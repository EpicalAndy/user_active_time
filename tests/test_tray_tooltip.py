"""
Тесты подсказки значка в трее: название с версией и одна метрика из каталога.

Запуск: `python -m pytest tests/test_tray_tooltip.py`
или как скрипт: `python tests/test_tray_tooltip.py`.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texts import TRAY_TITLE, TRAY_TOOLTIP_DAY_OFF  # noqa: E402
from modules.metrics import METRICS  # noqa: E402
from modules.widget import tray  # noqa: E402

STATS = {
    "is_working_day": True,
    "active_seconds": 5400,
    "activity_percent": 18.75,
    "full_day_seconds": 7200,
    "max_work_seconds": 28800,
    "activity_norm_seconds": 28800,
    "remaining_work_seconds": 21600,
    "recommended_remaining_seconds": 17640,
    "free_remaining_seconds": -900,
    "free_budget_seconds": 5760,
    "session_count": 3,
    "work_day_end": "17:00",
    "recommended_eta": "15:24",
}


# --- Текст подсказки ---


def test_metric_line_under_title():
    assert tray.tooltip_text("activity", STATS) == f"{TRAY_TITLE}\nАктивность: 1ч 30м (18.7%)"


def test_metric_without_percent():
    assert tray.tooltip_text("work_day_end", STATS) == f"{TRAY_TITLE}\nКонец дня: 17:00"


def test_no_metric_or_no_stats_is_title_only():
    assert tray.tooltip_text(tray.NO_METRIC, STATS) == TRAY_TITLE
    assert tray.tooltip_text("activity", None) == TRAY_TITLE
    assert tray.tooltip_text("нет_такой", STATS) == TRAY_TITLE


def test_day_off():
    stats = {**STATS, "is_working_day": False}
    assert tray.tooltip_text("activity", stats) == f"{TRAY_TITLE}\n{TRAY_TOOLTIP_DAY_OFF}"


def test_every_metric_fits_windows_limit_without_cutting():
    """Одна метрика влезает в 127 символов целиком — обрезка только страховка."""
    for metric in METRICS:
        text = tray.tooltip_text(metric.key, STATS)
        assert len(text) <= 127, metric.key
        assert text.count("\n") == 1, metric.key


def test_long_text_is_cut_to_limit():
    stats = {**STATS, "work_day_end": "x" * 300}
    assert len(tray.tooltip_text("work_day_end", stats)) == 127


# --- Сохранение выбора ---


def _with_tray_file(fn):
    saved = tray._TRAY_FILE
    with tempfile.TemporaryDirectory() as tmp:
        tray._TRAY_FILE = os.path.join(tmp, "tray.json")
        try:
            return fn()
        finally:
            tray._TRAY_FILE = saved


def test_default_when_nothing_saved():
    assert _with_tray_file(tray.load_tooltip_metric) == tray.DEFAULT_TOOLTIP_METRIC


def test_choice_survives_restart():
    def run():
        tray.save_tooltip_metric("free_time")
        first = tray.load_tooltip_metric()
        tray.save_tooltip_metric(tray.NO_METRIC)
        return first, tray.load_tooltip_metric()

    assert _with_tray_file(run) == ("free_time", tray.NO_METRIC)


def test_unknown_or_broken_choice_falls_back_to_default():
    def run():
        tray.save_tooltip_metric("нет_такой")
        unknown = tray.load_tooltip_metric()
        with open(tray._TRAY_FILE, "w", encoding="utf-8") as f:
            f.write("{битый")
        return unknown, tray.load_tooltip_metric()

    assert _with_tray_file(run) == (tray.DEFAULT_TOOLTIP_METRIC,) * 2


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
