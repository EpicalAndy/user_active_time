"""
Простой календарь-пикер: модальное окно с навигацией по месяцам и сеткой дней.
"""

import calendar
import datetime
import tkinter as tk
from collections.abc import Callable

from config import MAIN_FONT_SIZE
from constants import (
    CALENDAR_POPUP_TITLE,
    COLOR_DARK_BG,
    COLOR_LIGHT_FG,
    COLOR_MUTED,
    FONT_FAMILY,
)
from modules.ui_utils import center_on_parent

_MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
_WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class CalendarPopup:
    """Модальный календарь-пикер. Вызывает on_select(date) при выборе дня."""

    def __init__(
        self,
        parent: tk.Misc,
        on_select: Callable[[datetime.date], None],
        initial_date: datetime.date | None = None,
    ):
        self.on_select = on_select
        d = initial_date or datetime.date.today()
        self.year = d.year
        self.month = d.month

        self.win = tk.Toplevel(parent)
        self.win.title(CALENDAR_POPUP_TITLE)
        self.win.transient(parent)
        self.win.resizable(False, False)
        self.win.configure(bg=COLOR_DARK_BG)
        self.win.grab_set()
        # Восстанавливаем grab родителя при закрытии — иначе диалог-родитель
        # перестаёт быть модальным после выбора даты или закрытия календаря.
        self.win.bind("<Destroy>", self._on_destroy)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

        self._build_header()
        self._grid_frame = tk.Frame(self.win, bg=COLOR_DARK_BG)
        self._grid_frame.pack(padx=8, pady=(0, 8))
        self._render_grid()
        center_on_parent(self.win, parent)

    def _build_header(self):
        header = tk.Frame(self.win, bg=COLOR_DARK_BG)
        header.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(
            header, text="‹", command=self._prev_month, width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.LEFT)

        self._title_label = tk.Label(
            header, text="", bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
        )
        self._title_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

        tk.Button(
            header, text="›", command=self._next_month, width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.RIGHT)

    def _render_grid(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        self._title_label.configure(text=f"{_MONTH_NAMES[self.month - 1]} {self.year}")

        for col, name in enumerate(_WEEKDAY_NAMES):
            tk.Label(
                self._grid_frame, text=name,
                bg=COLOR_DARK_BG, fg=COLOR_MUTED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
                width=4,
            ).grid(row=0, column=col, padx=1, pady=1)

        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        weeks = cal.monthdayscalendar(self.year, self.month)
        for row, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                if day == 0:
                    continue
                tk.Button(
                    self._grid_frame, text=str(day), width=3,
                    font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
                    command=lambda d=day: self._select(d),
                ).grid(row=row, column=col, padx=1, pady=1)

    def _select(self, day: int):
        date = datetime.date(self.year, self.month, day)
        self.on_select(date)
        self.win.destroy()

    def _prev_month(self):
        if self.month == 1:
            self.year -= 1
            self.month = 12
        else:
            self.month -= 1
        self._render_grid()

    def _next_month(self):
        if self.month == 12:
            self.year += 1
            self.month = 1
        else:
            self.month += 1
        self._render_grid()

    def _on_destroy(self, event: tk.Event):
        if event.widget is not self.win:
            return
        try:
            parent = self.win.master
            if isinstance(parent, (tk.Toplevel, tk.Tk)):
                parent.grab_set()
        except tk.TclError:
            pass
