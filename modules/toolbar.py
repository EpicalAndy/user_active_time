"""
Панель инструментов виджета активности
"""

import tkinter as tk
from collections.abc import Callable
from typing import Literal

from config import MAIN_FONT_SIZE
from constants import (
    COLOR_DARKER_BG,
    COLOR_HOVER,
    COLOR_LIGHT_FG,
    COLOR_MUTED,
    COLOR_TOOLTIP_BG,
    COLOR_TOOLTIP_FG,
    FONT_FAMILY,
    REPORT_MENU_DAILY,
    REPORT_MENU_FOLDER,
    REPORT_MENU_PERIOD,
    REPORTS_MENU_LABEL,
    TOOLTIP_ADD_ACTIVE_TIME,
    TOOLTIP_OPEN_SETTINGS,
)

TOOLBAR_BG = COLOR_DARKER_BG
TOOLBAR_FG = COLOR_LIGHT_FG
TOOLBAR_HOVER_BG = COLOR_HOVER


class WidgetToolbar:
    """Горизонтальная панель инструментов с иконками и подсказками"""

    def __init__(
        self,
        parent: tk.Misc,
        on_add_active_time: Callable,
        on_open_reports: Callable,
        on_view_report: Callable,
        on_open_settings: Callable,
        on_period_report: Callable | None = None,
    ):
        self.frame = tk.Frame(parent, bg=TOOLBAR_BG, pady=2)

        # Слева: добавление активного времени
        self._add_button("⏱", TOOLTIP_ADD_ACTIVE_TIME, on_add_active_time, side=tk.LEFT)

        # Справа: настройки и выпадающий список «Отчёты»
        # Пакуем справа-налево, чтобы сохранить визуальный порядок.
        self._add_button("⚙", TOOLTIP_OPEN_SETTINGS, on_open_settings, side=tk.RIGHT)
        self._add_separator(side=tk.RIGHT)
        self._add_dropdown(
            REPORTS_MENU_LABEL,
            [
                (REPORT_MENU_FOLDER, on_open_reports),
                (REPORT_MENU_DAILY, on_view_report),
                (REPORT_MENU_PERIOD, on_period_report),
            ],
            side=tk.RIGHT,
        )

    def _add_button(
        self,
        icon: str,
        tooltip_text: str,
        command: Callable,
        side: Literal["left", "right", "top", "bottom"] = "left",
    ):
        btn = tk.Label(
            self.frame, text=icon,
            bg=TOOLBAR_BG, fg=TOOLBAR_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
            width=3, anchor=tk.CENTER,
        )
        btn.pack(side=side, fill=tk.Y)
        btn.bind("<Button-1>", lambda e: command())

        self._attach_hover(btn)
        self._attach_tooltip(btn, tooltip_text)
        return btn

    def _add_dropdown(
        self,
        label: str,
        items: list[tuple[str, Callable | None]],
        side: Literal["left", "right", "top", "bottom"] = "left",
    ):
        btn = tk.Label(
            self.frame, text=label,
            bg=TOOLBAR_BG, fg=TOOLBAR_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
            padx=8, anchor=tk.CENTER,
        )
        btn.pack(side=side, fill=tk.Y)

        menu = tk.Menu(btn, tearoff=0)
        for item_label, command in items:
            if command is None:
                menu.add_command(label=item_label, state=tk.DISABLED)
            else:
                menu.add_command(label=item_label, command=command)

        def on_click(_e):
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            menu.tk_popup(x, y)

        btn.bind("<Button-1>", on_click)
        self._attach_hover(btn)
        return btn

    def _add_separator(self, side: Literal["left", "right", "top", "bottom"] = "left"):
        sep = tk.Frame(self.frame, bg=COLOR_MUTED, width=1)
        sep.pack(side=side, fill=tk.Y, padx=6, pady=4)
        return sep

    def _attach_hover(self, widget: tk.Label):
        widget.bind("<Enter>", lambda _e: widget.configure(background=TOOLBAR_HOVER_BG), add="+")
        widget.bind("<Leave>", lambda _e: widget.configure(background=TOOLBAR_BG), add="+")

    def _attach_tooltip(self, widget: tk.Label, text: str):
        tip_window: list[tk.Toplevel | None] = [None]

        def on_enter(_e):
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)
            tk.Label(
                tw, text=text,
                bg=COLOR_TOOLTIP_BG, fg=COLOR_TOOLTIP_FG,
                font=(FONT_FAMILY, 9), padx=6, pady=2,
                relief=tk.SOLID, borderwidth=1,
            ).pack()
            tip_window[0] = tw

        def on_leave(_e):
            if tip_window[0] is not None:
                tip_window[0].destroy()
                tip_window[0] = None

        widget.bind("<Enter>", on_enter, add="+")
        widget.bind("<Leave>", on_leave, add="+")

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()
