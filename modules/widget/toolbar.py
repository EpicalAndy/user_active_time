"""
Панель инструментов виджета активности
"""

import tkinter as tk
from collections.abc import Callable
from typing import Literal

from config import MAIN_FONT_SIZE
from constants import (
    FONT_FAMILY,
    HELP_MENU_GITHUB,
    HELP_MENU_LABEL,
    HELP_MENU_README,
    REPORT_MENU_DAILY,
    REPORT_MENU_FOLDER,
    REPORT_MENU_HEATMAP,
    REPORT_MENU_LAST,
    REPORT_MENU_PERIOD,
    REPORT_MENU_TODAY,
    REPORTS_MENU_LABEL,
    TOOLTIP_ADD_ACTIVE_TIME,
    TOOLTIP_HELP,
    TOOLTIP_OPEN_SETTINGS,
    TOOLTIP_WIDGETS,
    WIDGETS_MENU_LABEL,
)
from modules import theme


class WidgetToolbar:
    """Горизонтальная панель инструментов с иконками и подсказками"""

    def __init__(
        self,
        parent: tk.Misc,
        on_add_active_time: Callable,
        on_open_reports: Callable,
        on_view_report: Callable,
        on_open_settings: Callable,
        on_open_readme: Callable,
        on_open_github: Callable,
        on_period_report: Callable | None = None,
        on_heatmap: Callable | None = None,
        on_today_report: Callable | None = None,
        on_last_report: Callable | None = None,
        on_add_widget: Callable[[str], None] | None = None,
        widget_types: list[tuple[str, str]] | None = None,
    ):
        self.frame = tk.Frame(parent, bg=theme.COLOR_DARKER_BG, pady=2)

        # Слева: добавление активного времени
        self._add_button("⏱", TOOLTIP_ADD_ACTIVE_TIME, on_add_active_time, side=tk.LEFT)

        # Слева: меню «Виджеты» — добавление мини-виджетов на рабочий стол.
        if on_add_widget is not None and widget_types:
            self._add_icon_dropdown(
                WIDGETS_MENU_LABEL,
                TOOLTIP_WIDGETS,
                [
                    (label, lambda k=key: on_add_widget(k))
                    for key, label in widget_types
                ],
                side=tk.LEFT,
            )

        # Справа: «Помощь», настройки и выпадающий список «Отчёты».
        # Пакуем справа-налево, чтобы сохранить визуальный порядок:
        # «Помощь» пакуется первой, поэтому оказывается правее настроек.
        self._add_icon_dropdown(
            HELP_MENU_LABEL,
            TOOLTIP_HELP,
            [
                (HELP_MENU_README, on_open_readme),
                (HELP_MENU_GITHUB, on_open_github),
            ],
            side=tk.RIGHT,
        )
        self._add_button("⚙", TOOLTIP_OPEN_SETTINGS, on_open_settings, side=tk.RIGHT)
        self._add_separator(side=tk.RIGHT)
        self._add_dropdown(
            REPORTS_MENU_LABEL,
            [
                (REPORT_MENU_TODAY, on_today_report),
                (REPORT_MENU_LAST, on_last_report),
                (REPORT_MENU_DAILY, on_view_report),
                None,
                (REPORT_MENU_FOLDER, on_open_reports),
                (REPORT_MENU_HEATMAP, on_heatmap),
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
            bg=theme.COLOR_DARKER_BG, fg=theme.COLOR_LIGHT_FG,
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
        items: list[tuple[str, Callable | None] | None],
        side: Literal["left", "right", "top", "bottom"] = "left",
    ):
        btn = tk.Label(
            self.frame, text=label,
            bg=theme.COLOR_DARKER_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
            padx=8, anchor=tk.CENTER,
        )
        btn.pack(side=side, fill=tk.Y)
        self._bind_menu(btn, items)
        self._attach_hover(btn)
        return btn

    def _add_icon_dropdown(
        self,
        icon: str,
        tooltip_text: str,
        items: list[tuple[str, Callable | None] | None],
        side: Literal["left", "right", "top", "bottom"] = "left",
    ):
        """Кнопка-иконка (как _add_button) с выпадающим меню и подсказкой."""
        btn = tk.Label(
            self.frame, text=icon,
            bg=theme.COLOR_DARKER_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
            width=3, anchor=tk.CENTER,
        )
        btn.pack(side=side, fill=tk.Y)
        self._bind_menu(btn, items)
        self._attach_hover(btn)
        self._attach_tooltip(btn, tooltip_text)
        return btn

    def _bind_menu(
        self,
        btn: tk.Label,
        items: list[tuple[str, Callable | None] | None],
    ):
        """Строит tk.Menu из items и раскрывает его под кнопкой по клику."""
        menu = tk.Menu(btn, tearoff=0)
        for item in items:
            if item is None:
                menu.add_separator()
                continue

            item_label, command = item
            if command is None:
                menu.add_command(label=item_label, state=tk.DISABLED)
            else:
                menu.add_command(label=item_label, command=command)

        def on_click(_e):
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            menu.tk_popup(x, y)

        btn.bind("<Button-1>", on_click)

    def _add_separator(self, side: Literal["left", "right", "top", "bottom"] = "left"):
        sep = tk.Frame(self.frame, bg=theme.COLOR_MUTED, width=1)
        sep.pack(side=side, fill=tk.Y, padx=6, pady=4)
        return sep

    def _attach_hover(self, widget: tk.Label):
        widget.bind("<Enter>", lambda _e: widget.configure(background=theme.COLOR_HOVER), add="+")
        widget.bind("<Leave>", lambda _e: widget.configure(background=theme.COLOR_DARKER_BG), add="+")

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
                bg=theme.COLOR_TOOLTIP_BG, fg=theme.COLOR_TOOLTIP_FG,
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

    def destroy(self):
        self.frame.destroy()
