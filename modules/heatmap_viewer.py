"""
Тепловая карта активности — месячный календарь с цветной заливкой по % активности.

Источник данных — те же дневные JSON-отчёты, что и для отчёта за период.
"""

import calendar
import datetime
import tkinter as tk

from config import MAIN_FONT_SIZE, MIN_ACTIVITY_THRESHOLD, RECOMMENDED_ACTIVITY_THRESHOLD
from constants import (
    COLOR_DARK_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_LIGHT_FG,
    COLOR_MUTED,
    COLOR_RED,
    COLOR_TOOLTIP_BG,
    COLOR_TOOLTIP_FG,
    COLOR_WHITE,
    COLOR_YELLOW,
    FONT_FAMILY,
    HEATMAP_CLOSE,
    HEATMAP_LEGEND_HIGH,
    HEATMAP_LEGEND_LOW,
    HEATMAP_LEGEND_MID,
    HEATMAP_LEGEND_NO_DATA,
    HEATMAP_TOOLTIP_ACTIVE,
    HEATMAP_TOOLTIP_NORM,
    HEATMAP_TOOLTIP_PERCENT,
    HEATMAP_WINDOW_TITLE,
)
from modules.period_report import _read_day_metrics, percent
from modules.ui_utils import center_on_screen
from utility import format_date_display, format_duration_short

_MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
_WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

_CELL_WIDTH = 5
_CELL_HEIGHT = 2


def _cell_color(active_pct: float | None) -> str:
    """Цвет ячейки по дневному % активности."""
    if active_pct is None:
        return COLOR_GRAY
    if active_pct >= RECOMMENDED_ACTIVITY_THRESHOLD:
        return COLOR_GREEN
    if active_pct >= MIN_ACTIVITY_THRESHOLD:
        return COLOR_YELLOW
    return COLOR_RED


class HeatmapViewer:
    """Окно тепловой карты с навигацией по месяцам."""

    def __init__(self, parent: tk.Misc):
        today = datetime.date.today()
        self.year = today.year
        self.month = today.month
        self._today = today

        self.win = tk.Toplevel(parent)
        self.win.title(HEATMAP_WINDOW_TITLE)
        self.win.transient(parent.winfo_toplevel())
        self.win.configure(bg=COLOR_DARK_BG)
        self.win.resizable(False, False)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

        self._build_ui()
        center_on_screen(self.win)

    def _build_ui(self):
        # --- Шапка с навигацией ---
        header = tk.Frame(self.win, bg=COLOR_DARK_BG)
        header.pack(fill=tk.X, padx=16, pady=(12, 4))

        tk.Button(
            header, text="‹", command=self._prev_month, width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.LEFT)

        self._title_label = tk.Label(
            header, text="", bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE + 1, "bold"),
        )
        self._title_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

        tk.Button(
            header, text="›", command=self._next_month, width=3,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.RIGHT)

        # --- Сетка ---
        self._grid_frame = tk.Frame(self.win, bg=COLOR_DARK_BG, padx=16, pady=8)
        self._grid_frame.pack()

        # --- Легенда ---
        self._build_legend()

        # --- Закрыть ---
        tk.Button(
            self.win, text=HEATMAP_CLOSE, command=self.win.destroy,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(pady=(4, 12))

        self._render_grid()

    def _render_grid(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        self._title_label.configure(text=f"{_MONTH_NAMES[self.month - 1]} {self.year}")

        # Заголовок дней недели
        for col, name in enumerate(_WEEKDAY_NAMES):
            tk.Label(
                self._grid_frame, text=name,
                bg=COLOR_DARK_BG, fg=COLOR_MUTED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
                width=_CELL_WIDTH,
            ).grid(row=0, column=col, padx=2, pady=(0, 4))

        # monthdatescalendar возвращает полные недели, включая дни смежных месяцев.
        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        weeks = cal.monthdatescalendar(self.year, self.month)
        for row, week in enumerate(weeks, start=1):
            for col, date in enumerate(week):
                self._draw_cell(row, col, date)

    def _draw_cell(self, row: int, col: int, date: datetime.date):
        in_current_month = (date.month == self.month)

        if not in_current_month:
            # Дни соседних месяцев — приглушённо, без тултипа
            cell = tk.Label(
                self._grid_frame, text=str(date.day),
                bg=COLOR_DARK_BG, fg=COLOR_MUTED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
                width=_CELL_WIDTH, height=_CELL_HEIGHT,
            )
            cell.grid(row=row, column=col, padx=2, pady=2)
            return

        metrics = _read_day_metrics(date)
        if metrics is None:
            bg = COLOR_GRAY
            fg = COLOR_LIGHT_FG
            tooltip = f"{format_date_display(date)}\n{HEATMAP_LEGEND_NO_DATA}"
        else:
            pct = percent(metrics["active_seconds"], metrics["max_work_seconds"])
            bg = _cell_color(pct)
            fg = COLOR_WHITE
            pct_str = f"{pct:.1f}%" if pct is not None else "—"
            tooltip = (
                f"{format_date_display(date)}\n"
                f"{HEATMAP_TOOLTIP_ACTIVE}: {format_duration_short(metrics['active_seconds'])}\n"
                f"{HEATMAP_TOOLTIP_NORM}: {format_duration_short(metrics['max_work_seconds'])}\n"
                f"{HEATMAP_TOOLTIP_PERCENT}: {pct_str}"
            )

        # Подсветить сегодняшнюю клетку рамкой
        if date == self._today:
            relief = tk.SOLID
            bd = 2
        else:
            relief = tk.FLAT
            bd = 0

        cell = tk.Label(
            self._grid_frame, text=str(date.day),
            bg=bg, fg=fg,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
            width=_CELL_WIDTH, height=_CELL_HEIGHT,
            relief=relief, bd=bd, highlightthickness=0,
        )
        cell.grid(row=row, column=col, padx=2, pady=2)
        self._attach_tooltip(cell, tooltip)

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
                bg=COLOR_TOOLTIP_BG, fg=COLOR_TOOLTIP_FG,
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

    def _build_legend(self):
        legend = tk.Frame(self.win, bg=COLOR_DARK_BG)
        legend.pack(pady=(4, 4))

        items = [
            (COLOR_GREEN, HEATMAP_LEGEND_HIGH.format(threshold=RECOMMENDED_ACTIVITY_THRESHOLD)),
            (COLOR_YELLOW, HEATMAP_LEGEND_MID.format(
                min=MIN_ACTIVITY_THRESHOLD, max=RECOMMENDED_ACTIVITY_THRESHOLD,
            )),
            (COLOR_RED, HEATMAP_LEGEND_LOW.format(threshold=MIN_ACTIVITY_THRESHOLD)),
            (COLOR_GRAY, HEATMAP_LEGEND_NO_DATA),
        ]
        for color, label in items:
            self._legend_item(legend, color, label)

    def _legend_item(self, parent: tk.Frame, color: str, text: str):
        frame = tk.Frame(parent, bg=COLOR_DARK_BG)
        frame.pack(side=tk.LEFT, padx=8)
        box = tk.Canvas(frame, width=14, height=14, bg=COLOR_DARK_BG, highlightthickness=0)
        box.pack(side=tk.LEFT, padx=(0, 4))
        box.create_rectangle(1, 1, 13, 13, fill=color, outline="")
        tk.Label(
            frame, text=text, bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(side=tk.LEFT)

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
