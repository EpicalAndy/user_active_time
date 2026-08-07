"""
Тесты мини-виджета «Метрики (полосы)».

Проверяется то, что не требует окна: разбор настройки набора полос, чтение
метрик (процент заполнения, подпись значения, цвет по шкале метрики) и выбор
читаемого цвета текста на полосе.

Запуск: `python -m pytest tests/test_metric_bars.py`
или как скрипт: `python tests/test_metric_bars.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import theme  # noqa: E402
from modules.widget.mini import bars  # noqa: E402
from modules.widget.mini.registry import default_opts  # noqa: E402

# Рабочий день: присутствие 5ч40м из 8ч, активность 83%, свободного 1ч30м.
STATS = {
    "is_working_day": True,
    "activity_percent": 83.0,
    "full_day_seconds": 20400,
    "max_work_seconds": 28800,
    "free_budget_seconds": 7200,
    "free_budget_min_seconds": 9900,
    "free_remaining_seconds": 5400,
    "free_remaining_min_seconds": 8100,
}


def read(key, stats=None):
    """Читает метрику при фиксированных порогах — тест не должен зависеть от конфига."""
    saved = {
        name: getattr(config, name) for name in (
            "RECOMMENDED_ACTIVITY_THRESHOLD", "MIN_ACTIVITY_THRESHOLD",
            "RECOMMENDED_WORK_TIME_THRESHOLD", "MIN_WORK_TIME_THRESHOLD",
        )
    }
    try:
        config.RECOMMENDED_ACTIVITY_THRESHOLD = 80
        config.MIN_ACTIVITY_THRESHOLD = 70
        config.RECOMMENDED_WORK_TIME_THRESHOLD = 100
        config.MIN_WORK_TIME_THRESHOLD = 80
        return bars._BARS[key]["read"](stats if stats is not None else STATS)
    finally:
        for name, value in saved.items():
            setattr(config, name, value)


# --- Набор полос ---


def test_default_is_all_bars_in_fixed_order():
    assert bars.selected_bars({}) == ["activity", "work_time", "free_time"]


def test_order_ignores_order_of_selection():
    """Порядок полос задаёт виджет, а не порядок кликов в диалоге."""
    assert bars.selected_bars({"metrics": ["free_time", "activity"]}) == [
        "activity", "free_time",
    ]


def test_unknown_keys_dropped():
    assert bars.selected_bars({"metrics": ["activity", "нет_такой"]}) == ["activity"]


def test_empty_selection_is_respected():
    """Пустой набор — валидное состояние: виджет покажет заглушку."""
    assert bars.selected_bars({"metrics": []}) == []


def test_broken_setting_falls_back_to_default():
    """widgets.json правится руками — мусор не должен ронять виджет."""
    assert bars.selected_bars({"metrics": None}) == bars.DEFAULT_BARS
    assert bars.selected_bars({"metrics": 42}) == bars.DEFAULT_BARS
    # Одиночная строка из старого конфига трактуется как набор из одного ключа.
    assert bars.selected_bars({"metrics": "activity"}) == ["activity"]


def test_default_opts_returns_independent_lists():
    """Иначе правка настроек одного виджета задела бы остальные."""
    first = default_opts("metric_bars")
    second = default_opts("metric_bars")
    assert first["metrics"] == second["metrics"]
    first["metrics"].append("сломали")
    assert "сломали" not in second["metrics"]


# --- Чтение метрик ---


def test_activity_bar_reads_percent_and_scale():
    pct, text, color = read("activity")
    assert pct == 83.0
    assert text == "83%"
    assert color == theme.COLOR_GREEN  # 83 >= RECOMMENDED_ACTIVITY_THRESHOLD (80)


def test_work_time_bar_is_share_of_work_hours():
    pct, text, color = read("work_time")
    assert round(pct, 1) == 70.8  # 20400 / 28800
    assert text == "71%"
    assert color == theme.COLOR_RED  # ниже MIN_WORK_TIME_THRESHOLD


def test_free_time_bar_shows_remaining_to_recommended():
    """Заполнение — от бюджета до минимальной нормы, подпись — остаток до рекомендуемой."""
    pct, text, color = read("free_time")
    assert round(pct, 1) == 81.8  # 8100 / 9900
    assert text == "1ч 30м"
    assert color == theme.COLOR_GREEN


def test_free_time_bar_shows_overspend_with_sign():
    overspent = {**STATS, "free_remaining_seconds": -900, "free_remaining_min_seconds": 1800}
    pct, text, color = read("free_time", overspent)
    assert text == "-0ч 15м"
    assert color == theme.COLOR_YELLOW


def test_bars_unavailable_without_norm():
    """Без нормы дня полосы нечем заполнять — виджет покажет прочерк."""
    assert read("work_time", {**STATS, "max_work_seconds": 0}) is None
    assert read("free_time", {**STATS, "free_budget_min_seconds": 0}) is None
    assert read("activity", {}) is None


def test_activity_over_hundred_is_reported_as_is():
    """Подрезает заливку отрисовка, а чтение метрики врать не должно."""
    pct, text, _ = read("activity", {**STATS, "activity_percent": 118.0})
    assert pct == 118.0
    assert text == "118%"


# --- Цвет текста на полосе ---


def test_ink_is_dark_on_light_background():
    assert bars.ink_for("#FFFFFF") == bars._INK_DARK
    assert bars.ink_for("#CFD8DC") == bars._INK_DARK  # трек полосы


def test_ink_is_light_on_dark_background():
    assert bars.ink_for("#2E7D32") == bars._INK_LIGHT  # зелёная заливка светлой темы
    assert bars.ink_for("#C62828") == bars._INK_LIGHT


def test_ink_readable_on_every_fill_of_both_themes():
    """Каждая заливка каждой темы должна получать контрастные чернила."""
    saved = theme.current_theme()
    try:
        for name in theme.available_themes():
            theme.set_theme(name)
            for color in (theme.COLOR_GREEN, theme.COLOR_YELLOW, theme.COLOR_RED,
                          theme.COLOR_LIGHT_GRAY):
                ink = bars.ink_for(color)
                assert abs(bars._luminance(ink) - bars._luminance(color)) > 0.3, (
                    f"{name}: {color} плохо читается чернилами {ink}"
                )
    finally:
        theme.set_theme(saved)


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
