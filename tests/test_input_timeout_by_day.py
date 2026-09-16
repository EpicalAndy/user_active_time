"""
Тесты таймаута неактивности по дням недели.

Таймаут задаётся на каждый день (как в корпоративных трекерах). Проверяется:
день без записи получает дефолт, ноль в дне отключает учёт простоя в этот
день (гэпы не вычитаются, отсчёта нет), нули во все дни выключают мониторинг,
а пересчёт активного времени берёт таймаут ДАТЫ, не сегодняшний. Плюс
миграция bootstrap: общий таймаут старого конфига раскладывается по дням.

Запуск: `python -m pytest tests/test_input_timeout_by_day.py`
или как скрипт: `python tests/test_input_timeout_by_day.py`.
"""

import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bootstrap  # noqa: E402
import config  # noqa: E402
from modules.session_monitor.activity import recompute_active  # noqa: E402
from utility import get_input_timeout, input_monitoring_enabled  # noqa: E402

MONDAY = datetime.date(2026, 9, 14)
FRIDAY = datetime.date(2026, 9, 18)
WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def with_timeouts(**by_day):
    """Подменяет таймауты по дням (остальные — 300) и возвращает функцию отката."""
    saved = dict(config.INPUT_ACTIVITY_TIMEOUT_BY_DAY)
    config.INPUT_ACTIVITY_TIMEOUT_BY_DAY.clear()
    config.INPUT_ACTIVITY_TIMEOUT_BY_DAY.update({**dict.fromkeys(WEEK, 300), **by_day})

    def restore():
        config.INPUT_ACTIVITY_TIMEOUT_BY_DAY.clear()
        config.INPUT_ACTIVITY_TIMEOUT_BY_DAY.update(saved)
    return restore


# --- Значение дня ---


def test_each_day_has_its_own_timeout():
    restore = with_timeouts(monday=120)
    try:
        assert get_input_timeout(MONDAY) == 120
        assert get_input_timeout(FRIDAY) == 300
    finally:
        restore()


def test_missing_day_falls_back_to_default():
    restore = with_timeouts()
    try:
        del config.INPUT_ACTIVITY_TIMEOUT_BY_DAY["friday"]
        assert get_input_timeout(FRIDAY) == config.DEFAULT_INPUT_ACTIVITY_TIMEOUT
    finally:
        restore()


def test_monitoring_enabled_if_any_day_counts_idle():
    restore = with_timeouts(**dict.fromkeys(WEEK, 0))
    try:
        assert not input_monitoring_enabled()
        config.INPUT_ACTIVITY_TIMEOUT_BY_DAY["wednesday"] = 60
        assert input_monitoring_enabled()
    finally:
        restore()


# --- Пересчёт по дате ---

_STATE = {
    "sessions": [{"start": "2026-09-14 09:00:00", "end": "2026-09-14 10:00:00"}],
    "idle": [{"from": "2026-09-14 09:30:00", "to": "2026-09-14 09:40:00"}],
    "log_entries": [],
}


def test_recompute_uses_timeout_of_that_date():
    """Гэп 10 минут: при таймауте 120 вычитается 8 мин, при 900 — ничего."""
    restore = with_timeouts(monday=120, friday=900)
    try:
        assert recompute_active(_STATE, MONDAY) == 3600 - (600 - 120)
        friday_state = {
            "sessions": [{"start": "2026-09-18 09:00:00", "end": "2026-09-18 10:00:00"}],
            "idle": [{"from": "2026-09-18 09:30:00", "to": "2026-09-18 09:40:00"}],
            "log_entries": [],
        }
        assert recompute_active(friday_state, FRIDAY) == 3600
    finally:
        restore()


def test_zero_timeout_ignores_idle_that_day():
    """Ноль в дне — простой не считается: гэп есть в записи, но не вычитается."""
    restore = with_timeouts(monday=0)
    try:
        assert recompute_active(_STATE, MONDAY) == 3600
    finally:
        restore()


# --- Миграция старого конфига ---

TEMPLATE = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.py"), encoding="utf-8").read()


def by_day_block(text: str) -> dict:
    m = re.search(r"^INPUT_ACTIVITY_TIMEOUT_BY_DAY = (\{[^}]+\})", text, re.M)
    return eval(m.group(1))  # noqa: S307 — текст словаря из конфига


def test_migration_spreads_general_timeout_over_days():
    merged = bootstrap._merge_config(TEMPLATE, 'INPUT_ACTIVITY_TIMEOUT = 210\nTHEME = "light"\n')
    assert by_day_block(merged) == dict.fromkeys(WEEK, 210)
    assert re.search(r"^INPUT_ACTIVITY_TIMEOUT =", merged, re.M) is None


def test_migration_keeps_general_zero_as_disabled():
    merged = bootstrap._merge_config(TEMPLATE, "INPUT_ACTIVITY_TIMEOUT = 0\n")
    assert by_day_block(merged) == dict.fromkeys(WEEK, 0)


def test_migration_fills_zero_days_with_general_and_keeps_set_ones():
    """Переходная схема: ноль в дне значил «общий» — он и подставляется."""
    old = 'INPUT_ACTIVITY_TIMEOUT = 210\nINPUT_ACTIVITY_TIMEOUT_BY_DAY = {"monday": 120, "friday": 0}\n'
    merged = bootstrap._merge_config(TEMPLATE, old)
    assert by_day_block(merged) == {**dict.fromkeys(WEEK, 210), "monday": 120}


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
