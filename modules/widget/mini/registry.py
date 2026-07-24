"""
Реестр типов мини-виджетов.

Единый источник для меню «Виджеты» (label) и для спавна по строковому типу
(class). Новый тип виджета добавляется одной записью.
"""

from constants import WIDGET_TYPE_ACTIVITY_PIE
from .pie import ActivityPieWidget

WIDGET_TYPES: dict[str, dict] = {
    "activity_pie": {"label": WIDGET_TYPE_ACTIVITY_PIE, "class": ActivityPieWidget},
}


def type_menu_items() -> list[tuple[str, str]]:
    """Список (type_key, label) для построения меню добавления виджетов."""
    return [(key, meta["label"]) for key, meta in WIDGET_TYPES.items()]
