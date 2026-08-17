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


# Тот же день для полосы-таймлайна: логин в 9:00, сейчас 12:00 (рабочее время
# 3ч), активность 9:00–10:30 и 11:00–11:30, ручное время 11:30–12:00.
TIMELINE_STATS = {
    **STATS,
    "active_seconds": 7200,
    "full_day_seconds": 10800,
    "timeline": {
        "start_seconds": 9 * 3600,
        "end_seconds": 12 * 3600,
        "segments": [
            (9 * 3600, 10 * 3600 + 1800, "active"),
            (10 * 3600 + 1800, 11 * 3600, "inactive"),
            (11 * 3600, 11 * 3600 + 1800, "active"),
            (11 * 3600 + 1800, 12 * 3600, "manual"),
        ],
    },
}


def at(share):
    """Индекс ячейки ленты по доле дня (0.0 — логин, 1.0 — «сейчас»)."""
    return int(bars._STRIP_CELLS * share)


def read(key, stats=None):
    """Читает метрику при фиксированных порогах — тест не должен зависеть от конфига."""
    saved = {
        name: getattr(config, name) for name in (
            "RECOMMENDED_ACTIVITY_THRESHOLD", "MIN_ACTIVITY_THRESHOLD",
            "RECOMMENDED_WORK_TIME_THRESHOLD", "MIN_WORK_TIME_THRESHOLD",
            "FREE_TIME_WARNING_PERCENT",
        )
    }
    try:
        config.RECOMMENDED_ACTIVITY_THRESHOLD = 80
        config.MIN_ACTIVITY_THRESHOLD = 70
        config.RECOMMENDED_WORK_TIME_THRESHOLD = 100
        config.MIN_WORK_TIME_THRESHOLD = 80
        config.FREE_TIME_WARNING_PERCENT = 20  # → жёлтая зона с 24м от бюджета 2ч
        return bars._BARS[key]["read"](stats if stats is not None else STATS)
    finally:
        for name, value in saved.items():
            setattr(config, name, value)


# --- Набор полос ---


def test_default_is_all_bars_in_fixed_order():
    assert bars.selected_bars({}) == ["activity", "work_time", "free_time", "timeline"]


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
    assert text == "70%"  # дробь отбрасывается, а не округляется
    assert color == theme.COLOR_RED  # ниже MIN_WORK_TIME_THRESHOLD


def test_free_time_bar_shows_remaining_to_recommended():
    """Заполнение — от бюджета до минимальной нормы, подпись — остаток до рекомендуемой."""
    pct, text, color = read("free_time")
    assert round(pct, 1) == 81.8  # 8100 / 9900
    assert text == "1ч 30м"
    assert color == theme.COLOR_GREEN


def test_free_time_bar_turns_yellow_near_the_end():
    ending = {**STATS, "free_remaining_seconds": 900, "free_remaining_min_seconds": 3600}
    pct, text, color = read("free_time", ending)
    assert text == "0ч 15м"
    assert color == theme.COLOR_YELLOW


def test_free_time_bar_shows_overspend_with_sign():
    """Перерасход — красный, хотя минимальная норма (полоса) ещё жива."""
    overspent = {**STATS, "free_remaining_seconds": -900, "free_remaining_min_seconds": 1800}
    pct, text, color = read("free_time", overspent)
    assert text == "-0ч 15м"
    assert color == theme.COLOR_RED


def test_timeline_bar_paints_the_whole_day_as_a_strip():
    """Полоса таймлайна — не заливка по проценту, а лента дня во всю ширину."""
    _, _, strip = read("timeline", TIMELINE_STATS)
    assert len(strip) == bars._STRIP_CELLS
    # День: активность 50%, простой до 66.7%, активность до 83.3%, ручное — хвост.
    assert strip[0] == theme.COLOR_GREEN
    assert strip[at(0.60)] == theme.COLOR_RED
    assert strip[at(0.75)] == theme.COLOR_GREEN
    assert strip[-1] == theme.COLOR_BLUE


def test_timeline_bar_value_is_share_of_work_time():
    """Значение — то же число, что в центре кольца таймлайна: 2ч из 3ч."""
    pct, text, _ = read("timeline", TIMELINE_STATS)
    assert round(pct, 1) == 66.7
    assert text == "66%"


def test_timeline_bar_value_is_not_clamped():
    """Ручное время честно поднимает активность выше рабочего времени."""
    over = {**TIMELINE_STATS, "active_seconds": 12600}  # 3ч30м из 3ч
    _, text, _ = read("timeline", over)
    assert text == "116%"


def test_timeline_bar_unavailable_without_a_day():
    """Ленту рисовать не из чего: нет данных, нет логина, нет рабочего времени."""
    assert read("timeline", {**TIMELINE_STATS, "timeline": None}) is None
    assert read("timeline", {**TIMELINE_STATS, "full_day_seconds": 0}) is None
    empty = {**TIMELINE_STATS["timeline"], "end_seconds": TIMELINE_STATS["timeline"]["start_seconds"]}
    assert read("timeline", {**TIMELINE_STATS, "timeline": empty}) is None


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
                          theme.COLOR_BLUE, theme.COLOR_LIGHT_GRAY):
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
