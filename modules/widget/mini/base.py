"""
Базовый мини-виджет рабочего стола.

Общий каркас для минимальных виджетов, отображающих ОДНУ метрику: окно без
рамки поверх остальных, перетаскивание с любого места, крестик закрытия,
контекстное меню (ПКМ) с удалением, сохранение позиции. Конкретный тип
реализует `_build()` (наполнение) и `update(stats)` (перерисовку по данным).

Все мини-виджеты живут на общем `tk.Tk()` root основного виджета — отдельного
mainloop у них нет, обновляются в такт метрикам конфигуратора (см. WidgetManager).
"""

import tkinter as tk
from collections.abc import Callable

from constants import FONT_FAMILY, WIDGET_REMOVE
from modules import theme

# Крестик закрытия. Живёт в правом верхнем углу — у всех мини-виджетов там
# пустое место (круг вписан в квадратную канву с отступом), поэтому кнопка
# ничего не перекрывает и не требует увеличивать окно.
_CLOSE_GLYPH = "✕"
_CLOSE_FONT_SIZE = 9
_CLOSE_INSET = 2      # отступ от края окна, px
_HIDE_DELAY_MS = 60   # пауза перед тем, как прятать крестик после <Leave>


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
        # Строго после _bind_events: иначе на крестик навесится drag с общего
        # обхода потомков и клик по нему превратится в перетаскивание.
        self._build_close_button()
        self._first_update()

    # --- Переопределяют подклассы ---

    def _build(self):
        """Наполняет окно (создаёт Canvas/лейблы). Реализует подкласс."""
        raise NotImplementedError

    def update(self, stats: dict):
        """Перерисовывает виджет по свежим stats. Реализует подкласс."""
        raise NotImplementedError

    def tick_second(self):
        """Секундный тик от менеджера.

        По умолчанию — ничего: метрики меняются медленно, и виджету хватает
        `update(stats)` раз в WIDGET_UPDATE_INTERVAL. Переопределяют те, кому
        нужна перерисовка каждую секунду (например, счётчик активности).
        """

    def _first_update(self):
        """Первичная отрисовка сразу после создания (до первого тика метрик)."""
        try:
            self.update(self.stats_provider())
        except Exception:
            pass

    def apply_opts(self, opts: dict):
        """Применяет новые настройки виджета и немедленно перерисовывает."""
        self.opts = opts or {}
        self._first_update()

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

    # --- Крестик закрытия ---

    def _build_close_button(self):
        """Создаёт крестик в правом верхнем углу окна.

        Кладётся через `place()`, а не в общий поток `pack()`, поэтому не
        участвует в расчёте `winfo_reqwidth/reqheight` — размер виджета
        остаётся прежним, крестик просто лежит поверх канвы в её пустом углу.

        Показывается только при наведении на виджет, чтобы не мозолить глаза:
        мини-виджет должен выглядеть как чистая картинка на рабочем столе.
        """
        # padx/pady/bd в ноль: у Label свои отступы по умолчанию, с ними
        # кнопка раздувается до ~18x21 и нижним углом задевает кольцо.
        self._close_btn = tk.Label(
            self.window, text=_CLOSE_GLYPH,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, _CLOSE_FONT_SIZE, "bold"), cursor="hand2",
            padx=0, pady=0, bd=0, highlightthickness=0,
        )
        self._close_btn.bind("<Button-1>", lambda _e: self._remove())
        self._close_btn.bind("<Enter>", self._highlight_close)
        self._close_btn.bind("<Leave>", self._unhighlight_close)

        # Наведение на любую часть виджета показывает крестик, уход — прячет.
        # add="+", чтобы не снести уже навешенные drag/меню обработчики.
        for w in self._all_widgets():
            w.bind("<Enter>", self._show_close, add="+")
            w.bind("<Leave>", self._hide_close_later, add="+")

    def _show_close(self, _event=None):
        # Цвета переназначаем при каждом показе: мини-виджеты не перекрашивают
        # себя при смене темы, а так крестик подхватит актуальную палитру.
        self._close_btn.configure(bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED)
        self._close_btn.place(
            relx=1.0, x=-_CLOSE_INSET, y=_CLOSE_INSET, anchor="ne",
        )

    def _hide_close_later(self, _event=None):
        """Прячет крестик, но не сразу.

        `<Leave>` прилетает и при переходе курсора между вложенными виджетами
        внутри окна (канва → крестик и обратно), поэтому решение принимаем на
        следующем тике — по фактическому положению курсора, а не по событию.
        """
        self.window.after(_HIDE_DELAY_MS, self._hide_close_if_outside)

    def _hide_close_if_outside(self):
        if not self.window.winfo_exists():
            return
        px, py = self.window.winfo_pointerxy()
        wx, wy = self.window.winfo_rootx(), self.window.winfo_rooty()
        inside = (
            wx <= px < wx + self.window.winfo_width()
            and wy <= py < wy + self.window.winfo_height()
        )
        if not inside:
            self._close_btn.place_forget()

    def _highlight_close(self, _event=None):
        self._close_btn.configure(fg=theme.COLOR_RED)

    def _unhighlight_close(self, _event=None):
        self._close_btn.configure(fg=theme.COLOR_MUTED)

    # --- Жизненный цикл ---

    def destroy(self):
        self.window.destroy()
