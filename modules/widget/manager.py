"""
Менеджер мини-виджетов рабочего стола.

Владеет живыми инстансами мини-виджетов, читает/пишет их реестр (widgets.json),
спавнит сохранённые при старте, добавляет/удаляет по запросу и раздаёт свежие
`stats` всем виджетам на каждом тике метрик конфигуратора.

Источник истины по составу — `self._items` (словарь записей реестра); живые
tk-инстансы лежат в `self._widgets` под теми же id.
"""

import tkinter as tk
import uuid
from collections.abc import Callable

from .mini.registry import WIDGET_TYPES
from .widget_store import load_widgets, save_widgets


class WidgetManager:
    """Жизненный цикл мини-виджетов: restore / add / remove / update."""

    def __init__(self, root: tk.Tk, stats_provider: Callable[[], dict]):
        self._root = root
        self._stats_provider = stats_provider
        self._widgets: dict[str, object] = {}
        self._items: dict[str, dict] = {}

    def restore(self):
        """Восстанавливает сохранённые виджеты при старте приложения."""
        for item in load_widgets():
            if item.get("type") not in WIDGET_TYPES or "id" not in item:
                continue
            self._spawn(item)

    def add(self, type_key: str):
        """Создаёт новый виджет указанного типа и сохраняет реестр."""
        if type_key not in WIDGET_TYPES:
            return
        widget_id = uuid.uuid4().hex[:8]
        x, y = self._default_position()
        item = {"id": widget_id, "type": type_key, "x": x, "y": y, "opts": {}}
        if self._spawn(item):
            self._persist()

    def remove(self, widget_id: str):
        """Убирает виджет и сохраняет реестр."""
        widget = self._widgets.pop(widget_id, None)
        self._items.pop(widget_id, None)
        if widget is not None:
            widget.destroy()
        self._persist()

    def update(self, stats: dict):
        """Раздаёт свежие stats всем живым виджетам."""
        for widget in self._widgets.values():
            try:
                widget.update(stats)
            except Exception:
                pass

    # --- Внутреннее ---

    def _spawn(self, item: dict) -> bool:
        """Создаёт инстанс виджета из записи реестра. True при успехе."""
        cls = WIDGET_TYPES[item["type"]]["class"]
        try:
            widget = cls(
                self._root,
                item["id"],
                self._stats_provider,
                self.remove,
                self._on_position_changed,
                int(item.get("x", 0)),
                int(item.get("y", 0)),
                item.get("opts") or {},
            )
        except Exception:
            return False
        self._widgets[item["id"]] = widget
        self._items[item["id"]] = item
        return True

    def _on_position_changed(self, widget_id: str, x: int, y: int):
        item = self._items.get(widget_id)
        if item is None:
            return
        item["x"] = x
        item["y"] = y
        self._persist()

    def _default_position(self) -> tuple[int, int]:
        """Правый верхний угол со смещением по числу уже открытых виджетов."""
        screen_w = self._root.winfo_screenwidth()
        offset = 30 * len(self._widgets)
        x = max(0, screen_w - 160 - offset)
        y = 40 + offset
        return x, y

    def _persist(self):
        save_widgets(list(self._items.values()))
