"""
Панель инструментов виджета активности
"""

import tkinter as tk
from collections.abc import Callable

from config import MAIN_FONT_SIZE

TOOLBAR_BG = "#34495E"
TOOLBAR_FG = "#ECF0F1"
TOOLBAR_HOVER_BG = "#5D6D7E"


class WidgetToolbar:
    """Горизонтальная панель инструментов с иконками и подсказками"""

    def __init__(
        self,
        parent: tk.Misc,
        on_open_reports: Callable,
        on_view_report: Callable,
        on_open_settings: Callable,
    ):
        self.frame = tk.Frame(parent, bg=TOOLBAR_BG, pady=2)

        self._add_button("\U0001F4C2", "Открыть отчёты", on_open_reports)
        self._add_button("\U0001F4CA", "Визуализация отчёта", on_view_report)
        self._add_button("\u2699", "Настройки", on_open_settings)

    def _add_button(self, icon: str, tooltip_text: str, command: Callable):
        btn = tk.Label(
            self.frame, text=icon,
            bg=TOOLBAR_BG, fg=TOOLBAR_FG,
            font=("Segoe UI", MAIN_FONT_SIZE), cursor="hand2",
            width=3, anchor=tk.CENTER,
        )
        btn.pack(side=tk.LEFT, fill=tk.Y)
        btn.bind("<Button-1>", lambda e: command())

        tip_window = None

        def on_enter(e):
            nonlocal tip_window
            btn.configure(bg=TOOLBAR_HOVER_BG)
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            tip_window = tw = tk.Toplevel(btn)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)
            tk.Label(
                tw, text=tooltip_text,
                bg="#FFFFE1", fg="#333333",
                font=("Segoe UI", 9), padx=6, pady=2,
                relief=tk.SOLID, borderwidth=1,
            ).pack()

        def on_leave(e):
            nonlocal tip_window
            btn.configure(bg=TOOLBAR_BG)
            if tip_window:
                tip_window.destroy()
                tip_window = None

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()
