"""
Тесты контекстного меню настроек мини-виджета.

Проверяется слой `plan()` — что попадёт в меню: группы, порядок пунктов и какие
из них отмечены активными (в меню активное значение рисуется жирным). Сама
раскладка в `tk.Menu` (`fill`) окна требует и тестами не покрыта.

Запуск: `python -m pytest tests/test_widget_menu.py`
или как скрипт: `python tests/test_widget_menu.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (  # noqa: E402
    WIDGET_OPT_CENTER_LABEL,
    WIDGET_OPT_CENTER_PERCENT,
    WIDGET_OPT_CENTER_TIME,
)
from modules.widget.mini import registry  # noqa: E402
from modules.widget.mini.options_menu import plan  # noqa: E402


def labels(group):
    return [item["label"] for item in group["items"]]


def active(group):
    return [item["value"] for item in group["items"] if item["active"]]


# --- Выбор одного значения ---


def test_choice_group_lists_all_values_in_schema_order():
    group = plan("activity_pie", {"center": "percent"})[0]
    assert group["key"] == "center"
    assert group["label"] == WIDGET_OPT_CENTER_LABEL
    assert labels(group) == [WIDGET_OPT_CENTER_PERCENT, WIDGET_OPT_CENTER_TIME]


def test_choice_marks_current_value():
    assert active(plan("activity_pie", {"center": "time"})[0]) == ["time"]


def test_choice_falls_back_to_type_default():
    """Настройки может не быть (новый виджет) — активен дефолт типа."""
    assert active(plan("activity_pie", {})[0]) == ["percent"]
    # У свободного времени дефолт другой — «Время».
    assert active(plan("free_time_pie", {})[0]) == ["time"]


def test_choice_with_unknown_value_marks_nothing():
    """widgets.json правится руками: мусор не должен «выбирать» пункт наугад."""
    assert active(plan("activity_pie", {"center": "нет_такого"})[0]) == []


# --- Набор значений ---


def test_multi_group_marks_selected_only():
    group = plan("metric_bars", {"metrics": ["activity", "free_time"]})[0]
    assert group["kind"] == registry.OPTION_MULTI
    assert active(group) == ["activity", "free_time"]


def test_multi_keeps_schema_order_not_selection_order():
    group = plan("metric_bars", {"metrics": ["free_time", "activity"]})[0]
    assert active(group) == ["activity", "free_time"]


def test_multi_empty_selection_is_respected():
    """Пустой набор — валидное состояние виджета, не повод подставлять дефолт."""
    assert active(plan("metric_bars", {"metrics": []})[0]) == []


def test_multi_broken_setting_falls_back_to_default():
    assert active(plan("metric_bars", {"metrics": None})[0]) == list(registry.DEFAULT_BARS)


# --- Границы ---


def test_type_without_options_gives_empty_menu():
    """У счётчика настраивать нечего — меню останется только с «Убрать виджет»."""
    assert plan("countdown", {}) == []


def test_unknown_type_gives_empty_menu():
    assert plan("нет_такого_типа", {}) == []


def test_unsupported_kind_is_skipped():
    """Настройку, которую в меню не выразить, пропускаем, а не падаем."""
    registry.WIDGET_TYPES["_test_type"] = {
        "label": "Тест",
        "class": object,
        "options": [
            {"key": "size", "kind": "number", "label": "Размер", "default": 1,
             "choices": []},
            registry.WIDGET_TYPES["activity_pie"]["options"][0],
        ],
    }
    try:
        groups = plan("_test_type", {})
        assert [g["key"] for g in groups] == ["center"]
    finally:
        del registry.WIDGET_TYPES["_test_type"]


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
