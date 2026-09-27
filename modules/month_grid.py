"""
Месячные календари: общие части и базовый класс сетки.

`MonthNavigator` (шапка «‹ Месяц Год ›» с листанием) и `grid_weekday_header`
(строка «Пн … Вс») — общие для всех календарей, включая пикер даты
(`calendar_popup.CalendarPopup`).

`MonthCalendarGrid` — каркас, переиспользуемый тепловой картой и календарём-
планировщиком: окно с навигацией по месяцам, строку дней недели, отрисовку
сетки через monthdatescalendar (с приглушёнными днями соседних месяцев),
тултипы и подсветку текущего дня.

Наследники переопределяют семантику ячейки:
    _cell_appearance(date) -> (bg, fg)   — цвет заливки и текста
    _cell_tooltip(date)    -> str | None — подсказка (None = без подсказки)
    _cell_clickable(date)  -> bool       — кликабельна ли ячейка
    _on_cell_click(date)                 — обработчик клика
    _build_legend()                      — необязательная легенда под сеткой
"""

import calendar
import datetime
import tkinter as tk
from collections.abc import Callable

from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from texts import MONTH_NAMES, WEEKDAY_SHORT_NAMES
from modules import theme
from modules.ui_utils import attach_tooltip, center_on_screen


class MonthNavigator:
    """Шапка «‹ Месяц Год ›»: хранит показываемый месяц и листает его.

    После каждого шага вызывает on_change() — владелец перерисовывает сетку.
    Фрейм шапки (`frame`) владелец размещает сам: отступы у окон разные.
    """

    def __init__(
        self,
        parent: tk.Misc,
        date: datetime.date,
        on_change: Callable[[], None],
        title_size: int = MAIN_FONT_SIZE,
    ):
        self.year = date.year
        self.month = date.month
        self._on_change = on_change

        self.frame = tk.Frame(parent, bg=theme.COLOR_DARK_BG)
        tk.Button(
            self.frame, text="‹", command=lambda: self.shift(-1), width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.LEFT)
        self._title_label = tk.Label(
            self.frame, text="", bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, title_size, "bold"),
        )
        self._title_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(
            self.frame, text="›", command=lambda: self.shift(1), width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.RIGHT)
        self._update_title()

    def shift(self, months: int):
        """Сдвигает показываемый месяц на months (±) и зовёт on_change."""
        index = self.year * 12 + (self.month - 1) + months
        self.year, month0 = divmod(index, 12)
        self.month = month0 + 1
        self._update_title()
        self._on_change()

    def _update_title(self):
        self._title_label.configure(text=f"{MONTH_NAMES[self.month - 1]} {self.year}")


def grid_weekday_header(frame: tk.Frame, width: int, padx, pady):
    """Строка «Пн … Вс» в нулевой строке grid-сетки календаря."""
    for col, name in enumerate(WEEKDAY_SHORT_NAMES):
        tk.Label(
            frame, text=name,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
            width=width,
        ).grid(row=0, column=col, padx=padx, pady=pady)


class MonthCalendarGrid:
    """Окно месячного календаря с навигацией. Базовый каркас без семантики ячеек."""

    CELL_WIDTH = 5
    CELL_HEIGHT = 2

    def __init__(self, parent: tk.Misc, title: str, close_text: str = "Закрыть"):
        self._today = datetime.date.today()
        self._close_text = close_text

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent.winfo_toplevel())
        self.win.configure(bg=theme.COLOR_DARK_BG)
        self.win.resizable(False, False)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

        self._build_ui()
        center_on_screen(self.win)

    # --- Каркас окна -------------------------------------------------------

    def _build_ui(self):
        self._nav = MonthNavigator(
            self.win, self._today, on_change=self._render_grid,
            title_size=MAIN_FONT_SIZE + 1,
        )
        self._nav.frame.pack(fill=tk.X, padx=16, pady=(12, 4))

        self._grid_frame = tk.Frame(self.win, bg=theme.COLOR_DARK_BG, padx=16, pady=8)
        self._grid_frame.pack()

        self._build_legend()

        tk.Button(
            self.win, text=self._close_text, command=self.win.destroy,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(pady=(4, 12))

        self._render_grid()

    def _render_grid(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        grid_weekday_header(self._grid_frame, self.CELL_WIDTH, padx=2, pady=(0, 4))

        # monthdatescalendar возвращает полные недели, включая дни соседних месяцев.
        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        weeks = cal.monthdatescalendar(self._nav.year, self._nav.month)
        for row, week in enumerate(weeks, start=1):
            for col, date in enumerate(week):
                self._draw_cell(row, col, date)

    def _draw_cell(self, row: int, col: int, date: datetime.date):
        if date.month != self._nav.month:
            # Дни соседних месяцев — приглушённо, без взаимодействия.
            tk.Label(
                self._grid_frame, text=str(date.day),
                bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
                width=self.CELL_WIDTH, height=self.CELL_HEIGHT,
            ).grid(row=row, column=col, padx=2, pady=2)
            return

        bg, fg = self._cell_appearance(date)
        relief, bd = (tk.SOLID, 2) if date == self._today else (tk.FLAT, 0)
        clickable = self._cell_clickable(date)

        cell = tk.Label(
            self._grid_frame, text=self._cell_text(date),
            bg=bg, fg=fg,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
            width=self.CELL_WIDTH, height=self.CELL_HEIGHT,
            relief=relief, bd=bd, highlightthickness=0,
            cursor="hand2" if clickable else "",
        )
        cell.grid(row=row, column=col, padx=2, pady=2)

        tooltip = self._cell_tooltip(date)
        if tooltip:
            attach_tooltip(cell, tooltip)
        if clickable:
            cell.bind("<Button-1>", lambda _e, d=date: self._on_cell_click(d))

    # --- Хуки для наследников (поведение по умолчанию — нейтральная ячейка) -

    def _cell_text(self, date: datetime.date) -> str:
        return str(date.day)

    def _cell_appearance(self, date: datetime.date) -> tuple[str, str]:
        return theme.COLOR_GRAY, theme.COLOR_LIGHT_FG

    def _cell_tooltip(self, date: datetime.date) -> str | None:
        return None

    def _cell_clickable(self, date: datetime.date) -> bool:
        return False

    def _on_cell_click(self, date: datetime.date):
        pass

    def _build_legend(self):
        """Необязательная легенда под сеткой. По умолчанию ничего."""
