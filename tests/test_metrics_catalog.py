"""
Тесты каталога метрик: одно описание метрики на все поверхности.

Текст (значение, парный процент, прочерк) и цвет по шкале должны быть такими,
какими их показывает тело виджета; флаги config — существовать.

Запуск: `python -m pytest tests/test_metrics_catalog.py`
или как скрипт: `python tests/test_metrics_catalog.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import theme  # noqa: E402
from modules.metrics import BY_KEY, EMPTY, METRICS, TITLE_METRICS  # noqa: E402

# 09:00–17:00 (8ч нормы, перерыв не учитываем), сейчас 11:00.
STATS = {
    "is_working_day": True,
    "active_seconds": 5400,             # 1ч 30м
    "activity_percent": 18.75,
    "full_day_seconds": 7200,           # 2ч
    "max_work_seconds": 28800,
    "activity_norm_seconds": 28800,
    "remaining_work_seconds": 21600,    # 6ч
    "recommended_remaining_seconds": 17640,
    "free_remaining_seconds": -900,     # перерасход 15 минут
    "free_budget_seconds": 5760,
    "session_count": 3,
    "work_day_end": "17:00",
    "recommended_eta": None,            # прогноза ещё нет
}


def with_thresholds(fn):
    """Фиксированные пороги — тест не зависит от конфига пользователя."""
    names = {
        "RECOMMENDED_ACTIVITY_THRESHOLD": 80, "MIN_ACTIVITY_THRESHOLD": 70,
        "RECOMMENDED_WORK_TIME_THRESHOLD": 100, "MIN_WORK_TIME_THRESHOLD": 80,
        "FREE_TIME_WARNING_PERCENT": 25,
    }
    saved = {name: getattr(config, name) for name in names}
    try:
        for name, value in names.items():
            setattr(config, name, value)
        return fn()
    finally:
        for name, value in saved.items():
            setattr(config, name, value)


# --- Состав каталога ---


def test_keys_are_unique_and_indexed():
    keys = [metric.key for metric in METRICS]
    assert len(keys) == len(set(keys))
    assert list(BY_KEY) == keys


def test_order_is_body_order():
    """Порядок каталога = порядок строк тела и галочек в настройках."""
    assert [metric.key for metric in METRICS] == [
        "activity", "work_time", "recommended_remaining", "remaining_time",
        "free_time", "session_count", "work_day_end", "recommended_eta",
    ]


def test_config_flags_exist():
    for metric in METRICS:
        assert hasattr(config, metric.show_attr), metric.show_attr
        if metric.percent is not None:
            assert hasattr(config, metric.show_percent_attr), metric.show_percent_attr
            assert metric.percent_label, metric.key


def test_title_metrics_refer_to_catalog():
    for attr, key, _show_value in TITLE_METRICS:
        assert hasattr(config, attr), attr
        assert key in BY_KEY, key


# --- Текст ---


def test_value_alone_and_with_percent():
    activity = BY_KEY["activity"]
    assert activity.render(STATS) == "1ч 30м"
    assert activity.render(STATS, percent=True) == "1ч 30м (18.7%)"


def test_percent_only():
    assert BY_KEY["activity"].render(STATS, value=False, percent=True) == "18.7%"
    assert BY_KEY["work_time"].render(STATS, value=False, percent=True) == "25.0%"


def test_missing_percent_is_dash_or_omitted():
    """Нормы нет: один процент — прочерк, в паре со значением — просто не дописывается."""
    no_norm = {**STATS, "max_work_seconds": 0}
    work_time = BY_KEY["work_time"]
    assert work_time.render(no_norm, value=False, percent=True) == EMPTY
    assert work_time.render(no_norm, percent=True) == "2ч 0м"


def test_negative_remainders():
    """Свободное время уходит в минус со знаком, остаток до конца дня — подрезается нулём."""
    assert BY_KEY["free_time"].render(STATS) == "-0ч 15м"
    assert BY_KEY["remaining_time"].render({**STATS, "remaining_work_seconds": -60}) == "0ч 0м"


def test_clock_values():
    assert BY_KEY["work_day_end"].render(STATS) == "17:00"
    assert BY_KEY["recommended_eta"].render(STATS) == EMPTY
    assert BY_KEY["recommended_eta"].value(STATS) is None


def test_empty_labels_inherit_main_ones():
    """Подпись задаётся только там, где отличается; иначе берётся основная."""
    work_time = BY_KEY["work_time"]
    assert work_time.short_label == work_time.settings_label == work_time.label
    assert work_time.settings_percent_label == work_time.percent_label
    # Где отличаются — свои.
    assert BY_KEY["work_day_end"].short_label != BY_KEY["work_day_end"].label
    assert BY_KEY["session_count"].settings_label != BY_KEY["session_count"].label
    assert BY_KEY["activity"].settings_percent_label != BY_KEY["activity"].percent_label


# --- Цвет ---


def test_colors_follow_scales():
    def colors():
        return {key: BY_KEY[key].color(STATS) for key in BY_KEY}

    got = with_thresholds(colors)
    assert got["activity"] == theme.COLOR_RED           # 18.7% активности
    assert got["recommended_eta"] == theme.COLOR_RED    # та же шкала активности
    assert got["work_time"] == theme.COLOR_RED          # 25% присутствия
    assert got["free_time"] == theme.COLOR_RED          # перерасход
    assert got["session_count"] is None                 # без шкалы


def test_color_uses_shown_precision():
    """Порог сверяется с показанным числом: 79.96% при 0 знаков — это 79%, жёлтый."""
    stats = {**STATS, "activity_percent": 79.96}
    activity = BY_KEY["activity"]
    assert with_thresholds(lambda: activity.color(stats, decimals=0)) == theme.COLOR_YELLOW
    assert with_thresholds(lambda: activity.color({**stats, "activity_percent": 80.0})) == theme.COLOR_GREEN


def test_work_time_scale_without_norm_has_no_color():
    stats = {**STATS, "max_work_seconds": 0}
    assert with_thresholds(lambda: BY_KEY["work_day_end"].color(stats)) is None


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
