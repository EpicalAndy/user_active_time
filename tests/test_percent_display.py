"""
Тесты показа процентов: число и его цвет должны сходиться.

Процент отображается с отброшенной дробью (не округляется вверх), и по этому же
усечённому числу берётся цвет — иначе метрика показывала «80%» жёлтым, потому
что на самом деле было 79.5%.

Запуск: `python -m pytest tests/test_percent_display.py`
или как скрипт: `python tests/test_percent_display.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import theme  # noqa: E402
from modules.widget.body import _color_for_percent  # noqa: E402
from modules.widget.mini.base import PERCENT_DECIMALS as MINI_DECIMALS  # noqa: E402
from utility import (  # noqa: E402
    calculate_activity_percent,
    format_percent,
    truncate_percent,
)

RECOMMENDED = 80
MINIMUM = 70


def color(pct, decimals=1):
    """Цвет по фиксированным порогам — тест не должен зависеть от конфига."""
    return _color_for_percent(pct, RECOMMENDED, MINIMUM, decimals)


# --- Усечение вместо округления ---


def test_fraction_is_dropped_not_rounded():
    assert format_percent(79.96) == "79.9%"
    assert format_percent(79.5, 0) == "79%"
    assert format_percent(99.99, 0) == "99%"


def test_exact_value_is_kept():
    assert format_percent(80.0) == "80.0%"
    assert format_percent(80.0, 0) == "80%"
    assert format_percent(0) == "0.0%"


def test_binary_noise_does_not_eat_a_tenth():
    """4ч из 5ч — это 80%, даже если в double получилось 79.99999999999999."""
    pct = calculate_activity_percent(4 * 3600, 5.0)
    assert format_percent(pct) == "80.0%"
    assert format_percent(pct, 0) == "80%"


def test_over_hundred_is_shown_as_is():
    assert format_percent(118.7) == "118.7%"


def test_overspend_stays_negative():
    """Свободное время уходит в минус — знак важнее лишней десятой."""
    assert format_percent(-12.34) == "-12.4%"
    # Крошечный минус не должен превращаться в «-0.0%».
    assert format_percent(-1e-9) == "0.0%"


# --- Цвет считается по показанному числу ---


def test_color_follows_shown_number_at_threshold():
    """79.96% печатается как «79.9%» — значит, порог 80 ещё не взят."""
    assert format_percent(79.96) == "79.9%"
    assert color(79.96) == theme.COLOR_YELLOW
    assert color(80.0) == theme.COLOR_GREEN


def test_mini_widget_color_matches_its_integer_percent():
    """У мини-виджетов дробной части нет вовсе — цвет считается по целому."""
    assert format_percent(79.5, MINI_DECIMALS) == "79%"
    assert color(79.5, MINI_DECIMALS) == theme.COLOR_YELLOW
    assert format_percent(69.9, MINI_DECIMALS) == "69%"
    assert color(69.9, MINI_DECIMALS) == theme.COLOR_RED


def test_green_exactly_when_shown_number_reaches_norm():
    """Сквозная проверка: цвет меняется ровно там, где показанное число берёт порог."""
    for hundredths in range(6000, 12001):
        pct = hundredths / 100
        for decimals in (1, MINI_DECIMALS):
            shown = truncate_percent(pct, decimals)
            expected = (
                theme.COLOR_GREEN if shown >= RECOMMENDED
                else theme.COLOR_YELLOW if shown >= MINIMUM
                else theme.COLOR_RED
            )
            assert color(pct, decimals) == expected, f"{pct} при {decimals} знаках"


def test_thresholds_are_read_from_config_dynamically():
    """Диалог настроек меняет пороги на лету — цвет должен идти следом."""
    saved = config.RECOMMENDED_ACTIVITY_THRESHOLD
    try:
        config.RECOMMENDED_ACTIVITY_THRESHOLD = 90
        assert _color_for_percent(
            85.0, config.RECOMMENDED_ACTIVITY_THRESHOLD, MINIMUM,
        ) == theme.COLOR_YELLOW
    finally:
        config.RECOMMENDED_ACTIVITY_THRESHOLD = saved


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
