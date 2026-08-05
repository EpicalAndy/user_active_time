"""
Менеджер мини-виджетов рабочего стола.

Владеет записями виджетов (`_items`: id → запись реестра) и живыми tk-окнами
(`_widgets`: id → инстанс, только для включённых). Каждая запись несёт флаг
`enabled`: выключенный виджет не отрисовывается, но его запись, настройки (`opts`)
и позиция сохраняются — чтобы включение восстанавливало всё как было.

Два уровня API:
- по id (`add`/`remove`/`update_opts`/`list_instances`) — «под капотом», допускает
  несколько экземпляров одного типа;
- по типу (`type_enabled`/`type_opts`/`set_type_enabled`/`update_type_opts`) — то,
  чем пользуется диалог управления: один настраиваемый виджет на тип.
"""

import tkinter as tk
import uuid
from collections.abc import Callable

from .mini.registry import WIDGET_TYPES, default_opts
from .widget_store import load_widgets, save_widgets


class WidgetManager:
    """Жизненный цикл мини-виджетов: restore / включение / настройки / persist."""

    def __init__(self, root: tk.Tk, stats_provider: Callable[[], dict]):
        self._root = root
        self._stats_provider = stats_provider
        self._widgets: dict[str, object] = {}  # только включённые (живые окна)
        self._items: dict[str, dict] = {}      # все записи (источник истины)

    def restore(self):
        """Восстанавливает сохранённые виджеты при старте (спавнит включённые)."""
        for item in load_widgets():
            if item.get("type") not in WIDGET_TYPES or "id" not in item:
                continue
            item.setdefault("enabled", True)
            item.setdefault("opts", default_opts(item["type"]))
            self._items[item["id"]] = item
            if item["enabled"]:
                self._spawn_live(item)

    # --- API по id (под капотом; допускает дубли одного типа) ---

    def add(self, type_key: str, opts: dict | None = None) -> str | None:
        """Создаёт новый включённый виджет типа. Возвращает id (или None)."""
        if type_key not in WIDGET_TYPES:
            return None
        widget_id = uuid.uuid4().hex[:8]
        x, y = self._default_position()
        item = {
            "id": widget_id, "type": type_key, "x": x, "y": y,
            "opts": opts or default_opts(type_key), "enabled": True,
        }
        self._items[widget_id] = item
        if not self._spawn_live(item):
            del self._items[widget_id]
            return None
        self._persist()
        return widget_id

    def remove(self, widget_id: str):
        """Полностью удаляет виджет (запись + окно) и сохраняет реестр."""
        self._despawn(widget_id)
        self._items.pop(widget_id, None)
        self._persist()

    def disable(self, widget_id: str):
        """Выключает виджет (прячет окно), сохраняя запись и настройки.

        Используется как действие «Убрать виджет» из контекстного меню самого
        виджета — визуально он исчезает, но настройки не теряются и восстановятся
        при включении через диалог.
        """
        item = self._items.get(widget_id)
        if item is None:
            return
        item["enabled"] = False
        self._despawn(widget_id)
        self._persist()

    def update_opts(self, widget_id: str, opts: dict):
        """Обновляет настройки конкретного виджета по id."""
        item = self._items.get(widget_id)
        if item is None:
            return
        item.setdefault("opts", {}).update(opts)
        self._apply_opts_live(widget_id, item["opts"])
        self._persist()

    def list_instances(self) -> list[dict]:
        """Все записи в порядке создания: [{id, type, label, opts, enabled}]."""
        out = []
        for widget_id, item in self._items.items():
            meta = WIDGET_TYPES.get(item["type"], {})
            out.append({
                "id": widget_id,
                "type": item["type"],
                "label": meta.get("label", item["type"]),
                "opts": item.get("opts", {}),
                "enabled": item.get("enabled", True),
            })
        return out

    # --- API по типу (для диалога: один виджет на тип) ---

    def type_enabled(self, type_key: str) -> bool:
        """Есть ли включённый (живой) виджет данного типа."""
        return any(
            it.get("enabled") and it["id"] in self._widgets
            for it in self._entries_for_type(type_key)
        )

    def type_opts(self, type_key: str) -> dict:
        """Текущие настройки типа (первой записи) или дефолты."""
        entries = self._entries_for_type(type_key)
        if entries:
            return dict(entries[0].get("opts", {}))
        return default_opts(type_key)

    def set_type_enabled(self, type_key: str, enabled: bool):
        """Включает/выключает виджет типа, сохраняя настройки при выключении."""
        entries = self._entries_for_type(type_key)
        if enabled:
            if not entries:
                self.add(type_key)  # add сам спавнит и persist'ит
                return
            for it in entries:
                it["enabled"] = True
                if it["id"] not in self._widgets:
                    self._spawn_live(it)
        else:
            for it in entries:
                it["enabled"] = False
                self._despawn(it["id"])
        self._persist()

    def update_type_opts(self, type_key: str, opts: dict):
        """Меняет настройки типа (создаёт выключенную запись, если виджета нет)."""
        entries = self._entries_for_type(type_key)
        if not entries:
            entries = [self._create_disabled_entry(type_key)]
        for it in entries:
            it.setdefault("opts", {}).update(opts)
            self._apply_opts_live(it["id"], it["opts"])
        self._persist()

    def update(self, stats: dict):
        """Раздаёт свежие stats всем живым виджетам."""
        for widget in self._widgets.values():
            try:
                widget.update(stats)
            except Exception:
                pass

    def tick_second(self):
        """Раздаёт секундный тик живым виджетам (для тех, кому мало stats)."""
        for widget in self._widgets.values():
            try:
                widget.tick_second()
            except Exception:
                pass

    # --- Внутреннее ---

    def _entries_for_type(self, type_key: str) -> list[dict]:
        return [it for it in self._items.values() if it["type"] == type_key]

    def _create_disabled_entry(self, type_key: str) -> dict:
        """Пустая выключенная запись типа — хранилище настроек до включения."""
        widget_id = uuid.uuid4().hex[:8]
        x, y = self._default_position()
        entry = {
            "id": widget_id, "type": type_key, "x": x, "y": y,
            "opts": default_opts(type_key), "enabled": False,
        }
        self._items[widget_id] = entry
        return entry

    def _spawn_live(self, item: dict) -> bool:
        """Создаёт живое окно из записи (запись уже в _items). True при успехе."""
        cls = WIDGET_TYPES[item["type"]]["class"]
        try:
            widget = cls(
                self._root,
                item["id"],
                self._stats_provider,
                self.disable,  # «Убрать виджет» из ПКМ = выключить (настройки живы)
                self._on_position_changed,
                int(item.get("x", 0)),
                int(item.get("y", 0)),
                item.get("opts") or {},
            )
        except Exception:
            return False
        self._widgets[item["id"]] = widget
        return True

    def _despawn(self, widget_id: str):
        widget = self._widgets.pop(widget_id, None)
        if widget is not None:
            widget.destroy()

    def _apply_opts_live(self, widget_id: str, opts: dict):
        widget = self._widgets.get(widget_id)
        if widget is not None:
            try:
                widget.apply_opts(opts)
            except Exception:
                pass

    def _on_position_changed(self, widget_id: str, x: int, y: int):
        item = self._items.get(widget_id)
        if item is None:
            return
        item["x"] = x
        item["y"] = y
        self._persist()

    def _default_position(self) -> tuple[int, int]:
        """Правый верхний угол со смещением по числу уже живых виджетов."""
        screen_w = self._root.winfo_screenwidth()
        offset = 30 * len(self._widgets)
        x = max(0, screen_w - 160 - offset)
        y = 40 + offset
        return x, y

    def _persist(self):
        save_widgets(list(self._items.values()))
