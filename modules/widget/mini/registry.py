"""
Реестр типов мини-виджетов.

Единый источник для UI (label, схема настроек) и для спавна по строковому типу
(class). Новый тип виджета добавляется одной записью; его настройки описываются
декларативно в `options` — диалог управления рендерит контролы по этой схеме,
не зная о конкретных типах.

Формат `options` — список опций, каждая:
    {"key": str, "label": str, "default": value, "choices": [(value, label), ...]}
"""

from constants import (
    WIDGET_OPT_CENTER_LABEL,
    WIDGET_OPT_CENTER_PERCENT,
    WIDGET_OPT_CENTER_TIME,
    WIDGET_TYPE_ACTIVITY_PIE,
    WIDGET_TYPE_COUNTDOWN,
    WIDGET_TYPE_FREE_TIME_PIE,
    WIDGET_TYPE_TIMELINE,
    WIDGET_TYPE_WORK_TIME_PIE,
)
from .countdown import CountdownWidget
from .freetime import FreeTimePieWidget
from .pie import ActivityPieWidget
from .timeline import TimelineWidget
from .worktime import WorkTimePieWidget

# Общая опция «что в центре кольца» — используют все кольцевые типы.
_CENTER_OPTION = {
    "key": "center",
    "label": WIDGET_OPT_CENTER_LABEL,
    "default": "percent",
    "choices": [
        ("percent", WIDGET_OPT_CENTER_PERCENT),
        ("time", WIDGET_OPT_CENTER_TIME),
    ],
}

# То же, но по умолчанию «Время»: у свободного времени осмысленный ответ —
# «сколько ещё осталось», а не доля бюджета.
_CENTER_OPTION_TIME_FIRST = {**_CENTER_OPTION, "default": "time"}

WIDGET_TYPES: dict[str, dict] = {
    "activity_pie": {
        "label": WIDGET_TYPE_ACTIVITY_PIE,
        "class": ActivityPieWidget,
        "options": [_CENTER_OPTION],
    },
    "work_time_pie": {
        "label": WIDGET_TYPE_WORK_TIME_PIE,
        "class": WorkTimePieWidget,
        "options": [_CENTER_OPTION],
    },
    "free_time_pie": {
        "label": WIDGET_TYPE_FREE_TIME_PIE,
        "class": FreeTimePieWidget,
        "options": [_CENTER_OPTION_TIME_FIRST],
    },
    "day_timeline": {
        "label": WIDGET_TYPE_TIMELINE,
        "class": TimelineWidget,
        "options": [_CENTER_OPTION],
    },
    # Счётчик показывает одно — обратный отсчёт, настраивать нечего.
    "countdown": {
        "label": WIDGET_TYPE_COUNTDOWN,
        "class": CountdownWidget,
        "options": [],
    },
}


def type_menu_items() -> list[tuple[str, str]]:
    """Список (type_key, label) доступных типов виджетов."""
    return [(key, meta["label"]) for key, meta in WIDGET_TYPES.items()]


def options_for(type_key: str) -> list[dict]:
    """Схема настроек типа (пустой список, если тип неизвестен/без настроек)."""
    meta = WIDGET_TYPES.get(type_key)
    return meta.get("options", []) if meta else []


def default_opts(type_key: str) -> dict:
    """Дефолтные значения настроек для нового виджета данного типа."""
    return {opt["key"]: opt["default"] for opt in options_for(type_key)}
