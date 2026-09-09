"""
Фасад инструментов: создание, меню, обновление, остановка.

Вызывающая сторона (виджет) не знает ни одного конкретного инструмента —
работает со списком, который отдаёт реестр.
"""

import tkinter as tk
from collections.abc import Callable

from .registry import TOOL_CLASSES


def create_tools(root: tk.Misc) -> list:
    """Создаёт и подключает все инструменты из реестра.

    Сломавшийся инструмент не должен уронить приложение: он просто не
    попадает в меню.
    """
    tools = []
    for tool_class in TOOL_CLASSES:
        try:
            tool = tool_class(root)
            tool.attach()
        except Exception as e:
            print(f"[TOOLS] Инструмент {tool_class.__name__} отключён: {e}")
            continue
        tools.append(tool)
    return tools


def menu_items(tools: list) -> list[tuple[str, Callable]]:
    """Плоский список пунктов меню «Инструменты» по всем инструментам."""
    items: list[tuple[str, Callable]] = []
    for tool in tools:
        items.extend(tool.menu_items())
    return items


def refresh_tools(tools: list):
    """Просит инструменты перечитать настройки (после диалога настроек)."""
    for tool in tools:
        try:
            tool.refresh()
        except Exception as e:
            print(f"[TOOLS] Не удалось обновить {type(tool).__name__}: {e}")


def detach_tools(tools: list):
    """Останавливает инструменты при выходе из приложения."""
    for tool in tools:
        try:
            tool.detach()
        except Exception as e:
            print(f"[TOOLS] Не удалось остановить {type(tool).__name__}: {e}")
