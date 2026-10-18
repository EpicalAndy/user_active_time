"""
Tkinter UI-хелперы.
"""

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable

from config import MAIN_FONT_SIZE
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
        tw, _label = _tooltip_window(widget, value)
        tw.wm_geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height() + offset_y}")
        tip[0] = tw

    def on_leave(_e):
        if tip[0] is not None:
            tip[0].destroy()
            tip[0] = None

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")


def attach_pointer_tooltip(
    widget: tk.Widget,
    text_at: Callable[[int, int], str | None],
    *,
    on_leave: Callable[[], None] | None = None,
    offset_y: int = 2,
) -> None:
    """Подсказка, текст которой зависит от точки под курсором (отрезок таймлайна).

    `text_at(x, y)` получает координаты курсора внутри виджета и возвращает
    текст или None — тогда подсказки нет. Зовётся на каждое движение мыши:
    окно подсказки создаётся один раз, дальше у него меняется только текст,
    и оно едет за курсором по горизонтали, держась под виджетом (у нижнего
    края экрана — над ним). `on_leave` — уборка при уходе курсора, например
    снять подсветку отрезка. С зажатой левой кнопкой (окно перетаскивают)
    подсказки нет — она бы ехала вслед за окном.
    """
    tip: list = [None, None]  # окно подсказки и метка в нём

    def hide():
        if tip[0] is not None:
            tip[0].destroy()
            tip[0] = tip[1] = None

    def on_motion(event):
        if event.state & _BUTTON1_MASK:
            leave(event)
            return
        value = text_at(event.x, event.y)
        if not value:
            hide()
            return
        if tip[0] is None:
            tip[0], tip[1] = _tooltip_window(widget, value)
        elif tip[1].cget("text") != value:
            tip[1].configure(text=value)
        tw = tip[0]
        tw.update_idletasks()
        width, height = tw.winfo_reqwidth(), tw.winfo_reqheight()
        x = max(0, min(event.x_root + 12, tw.winfo_screenwidth() - width))
        y = widget.winfo_rooty() + widget.winfo_height() + offset_y
        if y + height > tw.winfo_screenheight():
            y = widget.winfo_rooty() - height - offset_y
        tw.wm_geometry(f"+{x}+{y}")

    def leave(_e):
        hide()
        if on_leave is not None:
            on_leave()

    widget.bind("<Motion>", on_motion, add="+")
    widget.bind("<Leave>", leave, add="+")


# Бит зажатой левой кнопки мыши в event.state (Button1Mask; в Tk на Windows тот же).
_BUTTON1_MASK = 0x100


def _tooltip_window(widget: tk.Widget, text: str) -> tuple[tk.Toplevel, tk.Label]:
    """Окно подсказки с текстом; позицию задаёт вызывающий."""
    tw = tk.Toplevel(widget)
    tw.wm_overrideredirect(True)
    tw.attributes("-topmost", True)
    label = tk.Label(
        tw, text=text,
        bg=theme.COLOR_TOOLTIP_BG, fg=theme.COLOR_TOOLTIP_FG,
        font=(FONT_FAMILY, 9), padx=6, pady=3,
        justify=tk.LEFT,
        relief=tk.SOLID, borderwidth=1,
    )
    label.pack()
    return tw, label


def legend_item(parent: tk.Misc, color: str, text: str, padx: int = 8) -> None:
    """Элемент легенды в строку: цветной квадрат 12×12 и подпись справа."""
    frame = tk.Frame(parent, bg=theme.COLOR_DARK_BG)
    frame.pack(side=tk.LEFT, padx=padx)
    box = tk.Canvas(frame, width=14, height=14, bg=theme.COLOR_DARK_BG, highlightthickness=0)
    box.pack(side=tk.LEFT, padx=(0, 4))
    box.create_rectangle(1, 1, 13, 13, fill=color, outline="")
    tk.Label(
        frame, text=text, bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
        font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
    ).pack(side=tk.LEFT)


def restore_parent_grab_on_destroy(window: tk.Toplevel) -> None:
    """При закрытии модального window возвращает grab его родителю.

    Нужно вложенным модальным окнам (календарь поверх диалога, диалог дня
    поверх календаря): grab у Tk один на приложение, и без возврата родитель
    после закрытия дочернего окна перестаёт быть модальным.
    """
    def on_destroy(event: tk.Event):
        if event.widget is not window:
            return  # <Destroy> приходит и от дочерних виджетов окна
        try:
            parent = window.master
            if isinstance(parent, (tk.Toplevel, tk.Tk)):
                parent.grab_set()
        except tk.TclError:
            pass

    window.bind("<Destroy>", on_destroy)


def bold_pixel_width(text: str, size: int) -> int:
    """Ширина текста в пикселях при ЖИРНОМ начертании FONT_FAMILY этого размера.

    По этой (максимальной) ширине задаётся фиксированный слот лейбла, чтобы при
    переключении bold/normal раскладка не «прыгала». Требует существующего root.
    """
    return tkfont.Font(family=FONT_FAMILY, size=size, weight="bold").measure(text)
