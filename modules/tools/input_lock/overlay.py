"""
Плашка «Ввод заблокирован».

Полноэкранную заглушку не делаем намеренно: она прячет работу и пугает, а
сказать нужно ровно одно — какой комбинацией вернуть управление. Поэтому
маленькое окно поверх всех, по центру сверху, плюс остаток времени до
автоснятия, если оно включено.

Подсказка с комбинацией отключается отдельно от самой плашки (`hotkey_label`
= None): факт блокировки показать бывает нужно, а выход из неё — не всегда.

Пока активно окно с повышенными правами, плашка говорит, что блокировка не
действует (`set_bypassed`): ввод в такое окно Windows нашим хукам не отдаёт.

Все методы вызываются только из потока Tk.
"""

import tkinter as tk

from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from texts import (
    INPUT_LOCK_OVERLAY_BYPASSED,
    INPUT_LOCK_OVERLAY_BYPASSED_TITLE,
    INPUT_LOCK_OVERLAY_BYPASSED_UNKNOWN,
    INPUT_LOCK_OVERLAY_HINT,
    INPUT_LOCK_OVERLAY_LEFT,
    INPUT_LOCK_OVERLAY_TITLE,
)
from modules import theme


def _format_left(seconds: int) -> str:
    """Остаток в виде Ч:ММ:СС / ММ:СС.

    Здесь, в отличие от метрик дня, важны именно секунды: пользователь смотрит
    на плашку в тот момент, когда до автоснятия остались последние минуты.
    """
    hours, rest = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class LockOverlay:
    """Небольшое окно-напоминание, живущее только на время блокировки."""

    def __init__(self, root: tk.Misc):
        self._root = root
        self._window: tk.Toplevel | None = None
        self._title_label: tk.Label | None = None
        self._bypass_label: tk.Label | None = None
        self._hint_label: tk.Label | None = None
        self._left_label: tk.Label | None = None

    def show(self, hotkey_label: str | None):
        if self._window is not None:
            return

        window = tk.Toplevel(self._root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg=theme.COLOR_RED)
        # Плашка не должна перехватывать фокус: она только сообщает.
        window.attributes("-alpha", 0.92)

        frame = tk.Frame(window, bg=theme.COLOR_DARK_BG, padx=16, pady=10)
        frame.pack(padx=2, pady=2)

        self._title_label = tk.Label(
            frame, text=f"🔒 {INPUT_LOCK_OVERLAY_TITLE}",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE + 2, "bold"),
        )
        self._title_label.pack()

        # Пакуется под заголовком только на время обхода (set_bypassed).
        self._bypass_label = tk.Label(
            frame, text="",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        )

        if hotkey_label is not None:
            self._hint_label = tk.Label(
                frame, text=INPUT_LOCK_OVERLAY_HINT.format(hotkey=hotkey_label),
                bg=theme.COLOR_DARK_BG, fg=theme.COLOR_YELLOW,
                font=(FONT_FAMILY, MAIN_FONT_SIZE),
            )
            self._hint_label.pack(pady=(4, 0))

        self._left_label = tk.Label(
            frame, text="",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        )
        self._left_label.pack()

        self._window = window
        self._position(window)

    def _position(self, window: tk.Toplevel):
        """По центру сверху — там плашка реже перекрывает рабочее окно."""
        window.update_idletasks()
        x = (window.winfo_screenwidth() - window.winfo_reqwidth()) // 2
        y = max(0, window.winfo_screenheight() // 12)
        window.geometry(f"+{x}+{y}")

    def set_bypassed(self, process_name: str | None):
        """Переключает плашку в «блокировка не действует» и обратно.

        `process_name` — exe активного окна с повышенными правами ("" — имя
        неизвестно), None — такого окна больше нет, блокировка снова действует.
        """
        if self._window is None:
            return
        if process_name is None:
            self._title_label.configure(
                text=f"🔒 {INPUT_LOCK_OVERLAY_TITLE}", fg=theme.COLOR_LIGHT_FG,
            )
            self._bypass_label.pack_forget()
        else:
            self._title_label.configure(
                text=f"⚠ {INPUT_LOCK_OVERLAY_BYPASSED_TITLE}", fg=theme.COLOR_RED,
            )
            self._bypass_label.configure(
                text=INPUT_LOCK_OVERLAY_BYPASSED.format(process=process_name)
                if process_name else INPUT_LOCK_OVERLAY_BYPASSED_UNKNOWN,
            )
            self._bypass_label.pack(after=self._title_label, pady=(4, 0))
        # Ширина плашки поменялась — центрируем заново.
        self._position(self._window)

    def update_remaining(self, seconds: int | None):
        """Обновляет строку остатка до автоснятия (None — автоснятия нет)."""
        if self._left_label is None:
            return
        if seconds is None:
            self._left_label.pack_forget()
            return
        self._left_label.configure(
            text=INPUT_LOCK_OVERLAY_LEFT.format(time=_format_left(seconds)),
        )

    def hide(self):
        if self._window is None:
            return
        try:
            self._window.destroy()
        except tk.TclError:
            pass
        self._window = None
        self._title_label = None
        self._bypass_label = None
        self._hint_label = None
        self._left_label = None
