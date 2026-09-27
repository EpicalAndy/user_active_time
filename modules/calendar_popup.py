"""
Простой календарь-пикер: модальное окно с навигацией по месяцам и сеткой дней.
"""

import calendar
import datetime
import tkinter as tk
from collections.abc import Callable

from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from texts import CALENDAR_POPUP_TITLE
from modules import theme
from modules.month_grid import MonthNavigator, grid_weekday_header
from modules.ui_utils import center_on_parent, restore_parent_grab_on_destroy


class CalendarPopup:
    """Модальный календарь-пикер. Вызывает on_select(date) при выборе дня."""

    def __init__(
        self,
        parent: tk.Misc,
        on_select: Callable[[datetime.date], None],
        initial_date: datetime.date | None = None,
    ):
        self.on_select = on_select

        self.win = tk.Toplevel(parent)
        self.win.title(CALENDAR_POPUP_TITLE)
        self.win.transient(parent.winfo_toplevel())
        self.win.resizable(False, False)
        self.win.configure(bg=theme.COLOR_DARK_BG)
        self.win.grab_set()
        # Диалог-родитель снова модальный после выбора даты или закрытия.
        restore_parent_grab_on_destroy(self.win)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

        self._nav = MonthNavigator(
            self.win, initial_date or datetime.date.today(), on_change=self._render_grid,
        )
        self._nav.frame.pack(fill=tk.X, padx=8, pady=8)
        self._grid_frame = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        self._grid_frame.pack(padx=8, pady=(0, 8))
        self._render_grid()
        center_on_parent(self.win, parent)

    def _render_grid(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        grid_weekday_header(self._grid_frame, width=4, padx=1, pady=1)

        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        weeks = cal.monthdayscalendar(self._nav.year, self._nav.month)
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
        date = datetime.date(self._nav.year, self._nav.month, day)
        self.on_select(date)
        self.win.destroy()
