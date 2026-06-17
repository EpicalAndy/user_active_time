"""
Календарь рабочего времени — планировщик исключений из расписания.

Месячная сетка поверх MonthCalendarGrid: показывает, как для каждого дня
определяется дневной лимит, и позволяет кликом по дню задать переопределение
(свой лимит / выходной / заметку). Данные хранит modules.work_calendar,
резолвинг лимита — utility.get_work_hours.

Цвет ячейки:
    синий     — задан свой лимит часов (переопределение > 0)
    серый     — выходной (лимит 0: явный или по расписанию)
    тёмный фон — рабочий день по расписанию (переопределения нет)
Маркер «•» у числа — на день есть заметка.
"""

import datetime
import tkinter as tk

import utility
from config import MAIN_FONT_SIZE
from constants import (
    FONT_FAMILY,
    SCHEDULE_CALENDAR_TITLE,
    SCHEDULE_CLOSE,
    SCHEDULE_LEGEND_DAYOFF,
    SCHEDULE_LEGEND_DEFAULT,
    SCHEDULE_LEGEND_NOTE,
    SCHEDULE_LEGEND_OVERRIDE,
    SCHEDULE_TOOLTIP_DAYOFF,
    SCHEDULE_TOOLTIP_DEFAULT,
    SCHEDULE_TOOLTIP_HOURS_UNIT,
    SCHEDULE_TOOLTIP_LIMIT,
)
from modules import theme, work_calendar
from modules.day_schedule_dialog import DayScheduleDialog
from modules.month_grid import MonthCalendarGrid
from utility import format_date_display


def format_hours(hours: float) -> str:
    """Компактно форматирует часы: 8.5 → «8.5», 6.0 → «6», 8.25 → «8.25»."""
    return f"{hours:g}"


class ScheduleCalendar(MonthCalendarGrid):
    """Окно планировщика рабочего времени по датам."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent, SCHEDULE_CALENDAR_TITLE, SCHEDULE_CLOSE)

    def _cell_text(self, date: datetime.date) -> str:
        if work_calendar.get_note(date):
            return f"{date.day} •"
        return str(date.day)

    def _cell_appearance(self, date: datetime.date) -> tuple[str, str]:
        override = work_calendar.get_override_hours(date)
        if override is not None:
            if override == 0:
                return theme.COLOR_GRAY, theme.COLOR_WHITE
            return theme.COLOR_BLUE, theme.COLOR_WHITE
        # Переопределения нет — смотрим на эффективный лимит по расписанию.
        if utility.get_work_hours(date) == 0:
            return theme.COLOR_GRAY, theme.COLOR_LIGHT_FG
        return theme.COLOR_DARKER_BG, theme.COLOR_LIGHT_FG

    def _cell_tooltip(self, date: datetime.date) -> str | None:
        override = work_calendar.get_override_hours(date)
        effective = utility.get_work_hours(date)
        from_schedule = override is None

        lines = [format_date_display(date)]
        if effective == 0:
            suffix = f" ({SCHEDULE_TOOLTIP_DEFAULT})" if from_schedule else ""
            lines.append(f"{SCHEDULE_TOOLTIP_DAYOFF}{suffix}")
        else:
            label = SCHEDULE_TOOLTIP_DEFAULT if from_schedule else SCHEDULE_TOOLTIP_LIMIT
            lines.append(f"{label}: {format_hours(effective)} {SCHEDULE_TOOLTIP_HOURS_UNIT}")

        note = work_calendar.get_note(date)
        if note:
            lines.append(note)
        return "\n".join(lines)

    def _cell_clickable(self, date: datetime.date) -> bool:
        # Любой день можно настроить, включая будущие.
        return True

    def _on_cell_click(self, date: datetime.date):
        DayScheduleDialog(self.win, date, on_saved=self._render_grid)

    def _build_legend(self):
        legend = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        legend.pack(pady=(4, 4))

        items = [
            (theme.COLOR_BLUE, SCHEDULE_LEGEND_OVERRIDE),
            (theme.COLOR_GRAY, SCHEDULE_LEGEND_DAYOFF),
            (theme.COLOR_DARKER_BG, SCHEDULE_LEGEND_DEFAULT),
        ]
        for color, label in items:
            self._legend_item(legend, color, label)

        # Маркер заметки — текстом, без цветной плашки.
        tk.Label(
            legend, text=SCHEDULE_LEGEND_NOTE,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(side=tk.LEFT, padx=8)

    def _legend_item(self, parent: tk.Frame, color: str, text: str):
        frame = tk.Frame(parent, bg=theme.COLOR_DARK_BG)
        frame.pack(side=tk.LEFT, padx=8)
        box = tk.Canvas(frame, width=14, height=14, bg=theme.COLOR_DARK_BG, highlightthickness=0)
        box.pack(side=tk.LEFT, padx=(0, 4))
        box.create_rectangle(1, 1, 13, 13, fill=color, outline="")
        tk.Label(
            frame, text=text, bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(side=tk.LEFT)
