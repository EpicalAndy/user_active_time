"""
Базовый мини-виджет рабочего стола.

Общий каркас для минимальных виджетов, отображающих ОДНУ метрику: окно без
рамки поверх остальных, перетаскивание с любого места, крестик закрытия,
контекстное меню (ПКМ) с настройками виджета и удалением, сохранение позиции.
Конкретный тип реализует `_build()` (наполнение) и `update(stats)` (перерисовку
по данным).

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
# 11pt, не мельче: на 9pt хинтинг Segoe UI срезает верхние кончики глифа плоско,
# и крестик выглядит обрезанным сверху. Места в углу хватает с запасом.
_CLOSE_FONT_SIZE = 11
_CLOSE_INSET = 2      # отступ от края окна, px
_HIDE_DELAY_MS = 60   # пауза перед тем, как прятать крестик после <Leave>
# Смещение меню от точки клика, px: курсор должен оказаться у края меню,
# а не на первом пункте (см. _popup_menu).
_MENU_OFFSET = 3


class BaseMiniWidget:
    """Базовый мини-виджет: окно, drag, контекстное меню, позиция."""

    def __init__(
        self,
        root: tk.Tk,
        widget_id: str,
        type_key: str,
        stats_provider: Callable[[], dict],
        on_remove: Callable[[str], None],
        on_position_changed: Callable[[str, int, int], None],
        on_opts_changed: Callable[[str, dict], None],
        x: int,
        y: int,
        opts: dict,
    ):
        self.widget_id = widget_id
        # Тип нужен только для меню настроек: по нему берётся схема опций.
        self.type_key = type_key
        self.stats_provider = stats_provider
        self._on_remove = on_remove
        self._on_position_changed = on_position_changed
        self._on_opts_changed = on_opts_changed
        self.opts = opts or {}

        self._drag_x = 0
        self._drag_y = 0
        # Живёт, пока показано меню: tk-переменные пунктов и подменю (см.
        # options_menu.fill) — без ссылки их унесёт сборщик мусора.
        self._menu_keep: list = []

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

    def tick_blink(self):
        """Тик анимации мигания от менеджера (~500мс).

        По умолчанию — ничего. Переопределяют виджеты с мигающими элементами
        (счётчик активности мигает в такт с заголовком основного виджета).
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
        self._bind_menu_close(self._menu)

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
        """Показывает контекстное меню под курсором.

        Два обхода особенностей Windows, без них первый клик по пункту
        пропадает, а меню просто закрывается:

        * окно мини-виджета — overrideredirect и фокус само не берёт, поэтому
          первый клик по всплывшему меню уходит на активацию окна-владельца.
          `focus_force` делает окно активным заранее;
        * меню встаёт левым верхним углом ровно в точку клика, и курсор
          оказывается на первом пункте — то есть на заголовке группы, который
          `disabled`. Активным Tk такой пункт не делает, а клик без активного
          пункта у него означает «закрыть, ничего не вызывая» (`MenuInvoke` при
          `Priv(popup)` пустом — а на Windows он всегда пуст). Смещаем меню на
          пару пикселей: курсор оказывается у края, и первое же движение к
          пункту делает его активным по-честному.
        """
        self._rebuild_menu()
        self.window.focus_force()
        try:
            self._menu.tk_popup(event.x_root + _MENU_OFFSET, event.y_root + _MENU_OFFSET)
        finally:
            self._menu.grab_release()

    def _rebuild_menu(self):
        """Пересобирает меню под текущие настройки виджета.

        Именно на каждый показ, а не один раз при создании: те же настройки
        правит и диалог управления, а после его правок жирный (активное
        значение) должен остаться на месте.
        """
        # Импорт ленивый: options_menu тянет реестр типов, а реестр импортирует
        # классы виджетов, которые наследуют этот модуль — на верхнем уровне
        # получился бы цикл.
        from .options_menu import fill

        # Подменю прошлого показа: delete() снимает пункт-каскад, но окно
        # самого подменю оставляет — без destroy они копились бы с каждым ПКМ.
        for obj in self._menu_keep:
            if isinstance(obj, tk.Menu):
                obj.destroy()
        self._menu_keep = []

        self._menu.delete(0, tk.END)
        self._menu_keep = fill(
            self._menu, self.type_key, self.opts, self._change_opt,
        )
        for obj in self._menu_keep:
            if isinstance(obj, tk.Menu):
                self._bind_menu_close(obj)
        if self._menu.index(tk.END) is not None:
            self._menu.add_separator()
        self._menu.add_command(label=WIDGET_REMOVE, command=self._remove)

    def _change_opt(self, key: str, value):
        """Пункт меню изменил настройку.

        Наружу (менеджеру), а не в `self.opts`: он владеет записью виджета,
        сохраняет её и сам вернёт новые настройки через `apply_opts`.
        """
        self._on_opts_changed(self.widget_id, {key: value})

    def _bind_menu_close(self, menu: tk.Menu):
        """Закрытие меню правой кнопкой.

        Tk отдаёт `MenuInvoke` на отпускание ЛЮБОЙ кнопки (`bind Menu
        <ButtonRelease>` в menu.tcl), поэтому правый клик по меню не закрывал
        бы его, а выполнял пункт под курсором — с настройками в меню это значит
        «случайно переключил не то». Отпускание глушим совсем, а закрываем по
        нажатию: нажатие, открывшее меню, пришло в окно виджета, и сюда не
        попадает — ложных закрытий нет.
        """
        menu.bind("<ButtonRelease-3>", lambda _e: "break")
        menu.bind("<Button-3>", self._close_menu)

    def _close_menu(self, _event=None):
        self._menu.unpost()
        self._menu.grab_release()
        return "break"

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
        # padx/pady/bd в ноль: с дефолтными отступами Label кнопка раздувается
        # и нижним углом подходит вплотную к кольцу.
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
