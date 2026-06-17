"""
Базовый класс месячного календаря-сетки.

Содержит общий каркас, переиспользуемый тепловой картой и календарём-
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

from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from modules import theme
from modules.ui_utils import center_on_screen

_MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
_WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class MonthCalendarGrid:
    """Окно месячного календаря с навигацией. Базовый каркас без семантики ячеек."""

    CELL_WIDTH = 5
    CELL_HEIGHT = 2

    def __init__(self, parent: tk.Misc, title: str, close_text: str = "Закрыть"):
        today = datetime.date.today()
        self.year = today.year
        self.month = today.month
        self._today = today
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
        header = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        header.pack(fill=tk.X, padx=16, pady=(12, 4))

        tk.Button(
            header, text="‹", command=self._prev_month, width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.LEFT)

        self._title_label = tk.Label(
            header, text="", bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE + 1, "bold"),
        )
        self._title_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

        tk.Button(
            header, text="›", command=self._next_month, width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.RIGHT)

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

        self._title_label.configure(text=f"{_MONTH_NAMES[self.month - 1]} {self.year}")

        for col, name in enumerate(_WEEKDAY_NAMES):
            tk.Label(
                self._grid_frame, text=name,
                bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
                width=self.CELL_WIDTH,
            ).grid(row=0, column=col, padx=2, pady=(0, 4))

        # monthdatescalendar возвращает полные недели, включая дни соседних месяцев.
        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        weeks = cal.monthdatescalendar(self.year, self.month)
        for row, week in enumerate(weeks, start=1):
            for col, date in enumerate(week):
                self._draw_cell(row, col, date)

    def _draw_cell(self, row: int, col: int, date: datetime.date):
        if date.month != self.month:
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
            self._attach_tooltip(cell, tooltip)
        if clickable:
            cell.bind("<Button-1>", lambda _e, d=date: self._on_cell_click(d))

    def _attach_tooltip(self, widget: tk.Label, text: str):
        tip: list[tk.Toplevel | None] = [None]

        def on_enter(_e):
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 2
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)
            tk.Label(
                tw, text=text,
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

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

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
