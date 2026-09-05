"""
Tkinter UI-хелперы.
"""

import tkinter as tk
from collections.abc import Callable

from constants import FONT_FAMILY
from modules import theme


def center_on_parent(window: tk.Toplevel, parent: tk.Misc) -> None:
    """Центрирует window над parent. Удерживает в пределах экрана."""
    window.update_idletasks()
    dw = window.winfo_width()
    dh = window.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = max(0, min(x, sw - dw))
    y = max(0, min(y, sh - dh))
    window.geometry(f"+{x}+{y}")


def center_on_screen(window: tk.Toplevel) -> None:
    """Центрирует window на экране."""
    window.update_idletasks()
    w = window.winfo_width()
    h = window.winfo_height()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    window.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


def attach_tooltip(
    widget: tk.Widget,
    text: str | Callable[[], str | None],
    *,
    offset_y: int = 2,
) -> None:
    """Вешает на виджет всплывающую подсказку под ним.

    `text` — либо готовая строка, либо функция без аргументов: второе нужно
    там, где содержимое подсказки меняется по ходу жизни виджета (клетки
    недельной полосы обновляются каждый тик, перевешивать биндинги ради
    нового текста незачем). Пустая строка / None — подсказка не показывается.

    Биндинги вешаются с add="+", чтобы не затирать уже навешанные обработчики
    наведения (подсветка кнопок тулбара).
    """
    tip: list[tk.Toplevel | None] = [None]

    def on_enter(_e):
        value = text() if callable(text) else text
        if not value:
            return
        tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height() + offset_y}")
        tw.attributes("-topmost", True)
        tk.Label(
            tw, text=value,
            bg=theme.COLOR_TOOLTIP_BG, fg=theme.COLOR_TOOLTIP_FG,
            font=(FONT_FAMILY, 9), padx=6, pady=3,
            justify=tk.LEFT,
            relief=tk.SOLID, borderwidth=1,
        ).pack()
        tip[0] = tw

    def on_leave(_e):
        if tip[0] is not None:
            tip[0].destroy()
            tip[0] = None

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")
