"""
Базовый мини-виджет рабочего стола.

Общий каркас для минимальных виджетов, отображающих ОДНУ метрику: окно без
рамки поверх остальных, перетаскивание с любого места, контекстное меню (ПКМ)
с удалением, сохранение позиции. Конкретный тип реализует `_build()` (наполнение)
и `update(stats)` (перерисовку по данным).

Все мини-виджеты живут на общем `tk.Tk()` root основного виджета — отдельного
mainloop у них нет, обновляются в такт метрикам конфигуратора (см. WidgetManager).
"""

import tkinter as tk
from collections.abc import Callable

from constants import WIDGET_REMOVE
from modules import theme


class BaseMiniWidget:
    """Базовый мини-виджет: окно, drag, контекстное меню, позиция."""

    def __init__(
        self,
        root: tk.Tk,
        widget_id: str,
        stats_provider: Callable[[], dict],
        on_remove: Callable[[str], None],
        on_position_changed: Callable[[str, int, int], None],
        x: int,
        y: int,
        opts: dict,
    ):
        self.widget_id = widget_id
        self.stats_provider = stats_provider
        self._on_remove = on_remove
        self._on_position_changed = on_position_changed
        self.opts = opts or {}

        self._drag_x = 0
        self._drag_y = 0

        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        self.window.configure(bg=theme.COLOR_DARK_BG)

        self._build()
        self._position(x, y)
        self._bind_events()
        self._first_update()

    # --- Переопределяют подклассы ---

    def _build(self):
        """Наполняет окно (создаёт Canvas/лейблы). Реализует подкласс."""
        raise NotImplementedError

    def update(self, stats: dict):
        """Перерисовывает виджет по свежим stats. Реализует подкласс."""
        raise NotImplementedError

    def _first_update(self):
        """Первичная отрисовка сразу после создания (до первого тика метрик)."""
        try:
            self.update(self.stats_provider())
        except Exception:
            pass

    # --- Позиционирование ---

    def _position(self, x: int, y: int):
        self.window.update_idletasks()
        w = self.window.winfo_reqwidth()
        h = self.window.winfo_reqheight()
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = max(0, min(x, screen_w - w))
        y = max(0, min(y, screen_h - h))
        self.window.geometry(f"+{x}+{y}")

    # --- События (drag + контекстное меню) ---

    def _bind_events(self):
        """Вешает drag и ПКМ-меню на окно и все его дочерние виджеты."""
        self._menu = tk.Menu(self.window, tearoff=0)
        self._menu.add_command(label=WIDGET_REMOVE, command=self._remove)

        for w in self._all_widgets():
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._end_drag)
            w.bind("<Button-3>", self._popup_menu)

    def _all_widgets(self) -> list[tk.Misc]:
        """Окно + все потомки (рекурсивно) — чтобы события ловились везде."""
        result: list[tk.Misc] = [self.window]

        def walk(parent: tk.Misc):
            for child in parent.winfo_children():
                result.append(child)
                walk(child)

        walk(self.window)
        return result

    def _start_drag(self, event):
        self._drag_x = event.x_root - self.window.winfo_x()
        self._drag_y = event.y_root - self.window.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.window.geometry(f"+{x}+{y}")

    def _end_drag(self, _event):
        self._on_position_changed(
            self.widget_id, self.window.winfo_x(), self.window.winfo_y(),
        )

    def _popup_menu(self, event):
        self._menu.tk_popup(event.x_root, event.y_root)

    def _remove(self):
        self._on_remove(self.widget_id)

    # --- Жизненный цикл ---

    def destroy(self):
        self.window.destroy()
