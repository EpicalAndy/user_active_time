"""
Тулбар свёрнутого виджета, раскрываемый наведением и фокусом.

В свёрнутом виде («□») от окна остаётся один заголовок, тулбар спрятан. Он
выезжает, пока курсор над окном или фокус в нём (в том числе в открытом из
него диалоге), и прячется, когда уходит и то и другое.
"""

import tkinter as tk
from collections.abc import Callable

# Пауза перед тем, как спрятать тулбар: курсор, мимоходом задевший край окна
# или на миг ушедший с него, не должен заставлять тулбар мелькать.
HIDE_DELAY_MS = 300


class ToolbarReveal:
    """Решает, показан ли тулбар свёрнутого окна.

    Раскладку не трогает: при смене решения зовёт `on_change`, а окно само
    перепаковывает части, глядя на `shown`. `keep_open` — внешняя причина
    не прятать тулбар (раскрытое меню: курсор над ним, но не над окном).
    """

    def __init__(
        self,
        window: tk.Toplevel,
        on_change: Callable[[], None],
        keep_open: Callable[[], bool],
    ):
        self._window = window
        self._on_change = on_change
        self._keep_open = keep_open
        self._enabled = False
        self._hide_job: str | None = None
        self.shown = False
        # Биндинг на окне ловит события и его потомков: тег окна есть в их
        # bindtags. Само событие ничего не решает — только повод сверить
        # курсор и фокус.
        for sequence in ("<Enter>", "<Leave>", "<FocusIn>", "<FocusOut>"):
            window.bind(sequence, lambda _e: self.check(), add="+")

    def set_enabled(self, enabled: bool):
        """Включает раскрытие (виджет свёрнут) или выключает (развёрнут).

        `on_change` не зовётся — окно и так перекладывается при сворачивании.
        """
        self._enabled = enabled
        self._cancel_hide()
        self.shown = enabled and self._wanted()

    def check(self):
        """Сверяет видимость тулбара с курсором и фокусом.

        Зовётся из событий и раз в тик виджета — на случай, когда фокус ушёл
        из диалога в другое приложение и окну об этом не сказали.
        """
        if not self._enabled:
            return
        if self._wanted():
            self._cancel_hide()
            self._set_shown(True)
        elif self.shown and self._hide_job is None:
            self._hide_job = self._window.after(HIDE_DELAY_MS, self._hide)

    def _hide(self):
        self._hide_job = None
        if self._enabled and not self._wanted():
            self._set_shown(False)

    def _set_shown(self, shown: bool):
        if shown != self.shown:
            self.shown = shown
            self._on_change()

    def _cancel_hide(self):
        if self._hide_job is not None:
            self._window.after_cancel(self._hide_job)
            self._hide_job = None

    def _wanted(self) -> bool:
        return self._keep_open() or self._pointer_inside() or self._focus_inside()

    def _pointer_inside(self) -> bool:
        try:
            x, y = self._window.winfo_pointerxy()
            return self._owns(self._window.winfo_containing(x, y))
        except (KeyError, tk.TclError):
            # winfo_containing/focus_get падают с KeyError на служебных
            # клонах меню, которых нет в словаре виджетов tkinter.
            return False

    def _focus_inside(self) -> bool:
        try:
            return self._owns(self._window.focus_get())
        except (KeyError, tk.TclError):
            return False

    def _owns(self, widget: tk.Misc | None) -> bool:
        """Виджет — само окно или его потомок (подсказка, диалог, меню).

        Сравнение с точкой: мини-виджет «.!toplevel2» тоже начинается
        с «.!toplevel», но к окну не относится.
        """
        if widget is None:
            return False
        window_path, path = str(self._window), str(widget)
        return path == window_path or path.startswith(window_path + ".")
