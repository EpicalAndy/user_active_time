"""
Тесты мини-виджета «Отметки времени (список)».

Проверяется то, что не требует окна: разбор настройки набора отметок и чтение
самих отметок (значение + цвет). Главное свойство виджета — он не изобретает
своих шкал: каждая отметка красится ровно так же, как та же метрика в теле
основного виджета («До рекомендуемой активности» — по проценту активности, «Конец дня» —
по проценту присутствия).

Запуск: `python -m pytest tests/test_time_marks.py`
или как скрипт: `python tests/test_time_marks.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import theme  # noqa: E402
from modules.widget.mini import marks  # noqa: E402
from modules.widget.mini.registry import default_opts  # noqa: E402

# Рабочий день 09:00–17:00, сейчас 11:00: присутствие 2ч из 8ч (25%),
# активность 45% от нормы, прогноз выхода на норму в 15:24.
STATS = {
    "is_working_day": True,
    "activity_percent": 45.0,
    "full_day_seconds": 7200,
    "max_work_seconds": 28800,
    "recommended_eta": "15:24",
    "work_day_end": "17:00",
}


def read(key, stats=None):
    """Читает отметку при фиксированных порогах — тест не зависит от конфига."""
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
        return marks._MARKS[key]["read"](stats if stats is not None else STATS)
    finally:
        for name, value in saved.items():
            setattr(config, name, value)


# --- Набор отметок ---


def test_default_is_all_marks_in_fixed_order():
    assert marks.selected_marks({}) == ["recommended_eta", "work_day_end"]


def test_order_ignores_order_of_selection():
    """Порядок строк задаёт виджет, а не порядок кликов в диалоге."""
    assert marks.selected_marks({"marks": ["work_day_end", "recommended_eta"]}) == [
        "recommended_eta", "work_day_end",
    ]


def test_unknown_keys_dropped():
    assert marks.selected_marks({"marks": ["work_day_end", "нет_такой"]}) == ["work_day_end"]


def test_empty_selection_is_respected():
    """Пустой набор — валидное состояние: виджет покажет заглушку."""
    assert marks.selected_marks({"marks": []}) == []


def test_broken_setting_falls_back_to_default():
    """widgets.json правится руками — мусор не должен ронять виджет."""
    assert marks.selected_marks({"marks": None}) == marks.DEFAULT_MARKS
    assert marks.selected_marks({"marks": 42}) == marks.DEFAULT_MARKS
    # Одиночная строка трактуется как набор из одного ключа.
    assert marks.selected_marks({"marks": "work_day_end"}) == ["work_day_end"]


def test_default_opts_returns_independent_lists():
    """Иначе правка настроек одного виджета задела бы остальные."""
    first = default_opts("time_marks")
    second = default_opts("time_marks")
    assert first["marks"] == second["marks"]
    first["marks"].append("сломали")
    assert "сломали" not in second["marks"]


# --- Чтение отметок ---


def test_eta_reads_time_and_activity_scale():
    """Значение — как есть из stats, цвет — по проценту активности (45% → красный)."""
    value, color = read("recommended_eta")
    assert value == "15:24"
    assert color == theme.COLOR_RED


def test_eta_color_follows_activity_thresholds():
    """Те же три зоны, что у метрик активности в теле основного виджета."""
    zones = {
        45.0: theme.COLOR_RED,
        72.5: theme.COLOR_YELLOW,
        81.0: theme.COLOR_GREEN,
        # Ровно на пороге — уже зелёный.
        80.0: theme.COLOR_GREEN,
    }
    for percent, expected in zones.items():
        _, color = read("recommended_eta", {**STATS, "activity_percent": percent})
        assert color == expected, percent


def test_eta_percent_is_truncated_like_the_shown_number():
    """Мини-виджеты сверяют порог с процентом без дробной части (79.96% → 79%)."""
    _, color = read("recommended_eta", {**STATS, "activity_percent": 79.96})
    assert color == theme.COLOR_YELLOW


def test_work_day_end_reads_time_and_work_time_scale():
    """Значение — как есть из stats, цвет — по присутствию (25% от нормы → красный)."""
    value, color = read("work_day_end")
    assert value == "17:00"
    assert color == theme.COLOR_RED


def test_work_day_end_color_follows_work_time_thresholds():
    """Отметка стоит на месте, цвет подтягивается к ней по мере присутствия."""
    zones = {
        7200: theme.COLOR_RED,       # 2ч из 8ч — 25%
        23040: theme.COLOR_YELLOW,   # 6ч24м — 80%, минимальный порог взят
        28800: theme.COLOR_GREEN,    # 8ч — день отсижен целиком
    }
    for present, expected in zones.items():
        _, color = read("work_day_end", {**STATS, "full_day_seconds": present})
        assert color == expected, present


def test_work_day_end_ignores_activity():
    """Присутствие и активность — разные шкалы: активность на цвет не влияет."""
    _, low = read("work_day_end", {**STATS, "activity_percent": 10.0})
    _, high = read("work_day_end", {**STATS, "activity_percent": 99.0})
    assert low == high == theme.COLOR_RED


def test_missing_values_are_not_read():
    """Момента ещё нет — отметка не читается, виджет поставит прочерк."""
    assert read("recommended_eta", {**STATS, "recommended_eta": None}) is None
    assert read("work_day_end", {**STATS, "work_day_end": None}) is None


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
