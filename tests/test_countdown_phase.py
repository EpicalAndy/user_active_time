"""
Тесты фазы счётчика до неактивности.

Фазу по остатку считает одна функция (`countdown_indicator.countdown_phase`),
и по ней красятся оба счётчика — в заголовке виджета и мини-виджет «Счётчик».

Запуск: `python -m pytest tests/test_countdown_phase.py`
или как скрипт: `python tests/test_countdown_phase.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules.widget.countdown_indicator import (  # noqa: E402
    COUNTDOWN_NORMAL,
    COUNTDOWN_WARNING,
    COUNTDOWN_ZERO,
    countdown_phase,
)


def _with_warning(seconds, fn):
    saved = config.COUNTDOWN_WARNING_SECONDS
    config.COUNTDOWN_WARNING_SECONDS = seconds
    try:
        return fn()
    finally:
        config.COUNTDOWN_WARNING_SECONDS = saved


def test_text_is_minutes_and_seconds():
    assert _with_warning(0, lambda: countdown_phase(125))[0] == "02:05"
    assert _with_warning(0, lambda: countdown_phase(0))[0] == "00:00"


def test_zero_means_inactive():
    assert _with_warning(30, lambda: countdown_phase(0)) == ("00:00", COUNTDOWN_ZERO)


def test_warning_up_to_threshold_inclusive():
    assert _with_warning(30, lambda: countdown_phase(30))[1] == COUNTDOWN_WARNING
    assert _with_warning(30, lambda: countdown_phase(1))[1] == COUNTDOWN_WARNING
    assert _with_warning(30, lambda: countdown_phase(31))[1] == COUNTDOWN_NORMAL


def test_zero_threshold_disables_warning():
    assert _with_warning(0, lambda: countdown_phase(5))[1] == COUNTDOWN_NORMAL
    # Ноль остаётся нулём и без предупреждения.
    assert _with_warning(0, lambda: countdown_phase(0))[1] == COUNTDOWN_ZERO


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
