"""
Пакет виджета активности.

Внешние потребители импортируют ActivityWidget / is_widget_enabled отсюда:
    from modules.widget import ActivityWidget, is_widget_enabled
"""

from .widget import ActivityWidget, is_widget_enabled

__all__ = ["ActivityWidget", "is_widget_enabled"]
