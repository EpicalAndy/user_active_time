"""
Тепловая карта активности — месячный календарь с цветной заливкой по % активности.

Источник данных — те же дневные JSON-отчёты, что и для отчёта за период.
Каркас сетки (навигация, тултипы, подсветка «сегодня») — в MonthCalendarGrid.
"""

import datetime
import tkinter as tk

from config import MAIN_FONT_SIZE, MIN_ACTIVITY_THRESHOLD, RECOMMENDED_ACTIVITY_THRESHOLD
from constants import (
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
from modules import theme
from modules.month_grid import MonthCalendarGrid
from modules.period_report import _read_day_metrics, get_report_path, percent
from modules.report_viewer import ReportViewer
from utility import format_date_display, format_duration_short


def _cell_color(active_pct: float | None) -> str:
    """Цвет ячейки по дневному % активности."""
    if active_pct is None:
        return theme.COLOR_GRAY
    if active_pct >= RECOMMENDED_ACTIVITY_THRESHOLD:
        return theme.COLOR_GREEN
    if active_pct >= MIN_ACTIVITY_THRESHOLD:
        return theme.COLOR_YELLOW
    return theme.COLOR_RED


class HeatmapViewer(MonthCalendarGrid):
    """Окно тепловой карты с навигацией по месяцам."""

    def __init__(self, parent: tk.Misc):
        # Кэш дневных метрик: каждая ячейка опрашивается тремя хуками
        # (цвет/тултип/кликабельность) — без кэша это тройное чтение с диска.
        self._metrics_cache: dict[datetime.date, dict | None] = {}
        super().__init__(parent, HEATMAP_WINDOW_TITLE, HEATMAP_CLOSE)

    def _metrics(self, date: datetime.date) -> dict | None:
        if date not in self._metrics_cache:
            self._metrics_cache[date] = _read_day_metrics(date)
        return self._metrics_cache[date]

    def _cell_appearance(self, date: datetime.date) -> tuple[str, str]:
        metrics = self._metrics(date)
        if metrics is None:
            return theme.COLOR_GRAY, theme.COLOR_LIGHT_FG
        pct = percent(metrics["active_seconds"], metrics["max_work_seconds"])
        return _cell_color(pct), theme.COLOR_WHITE

    def _cell_tooltip(self, date: datetime.date) -> str | None:
        metrics = self._metrics(date)
        if metrics is None:
            return f"{format_date_display(date)}\n{HEATMAP_LEGEND_NO_DATA}"
        pct = percent(metrics["active_seconds"], metrics["max_work_seconds"])
        pct_str = f"{pct:.1f}%" if pct is not None else "—"
        return (
            f"{format_date_display(date)}\n"
            f"{HEATMAP_TOOLTIP_ACTIVE}: {format_duration_short(metrics['active_seconds'])}\n"
            f"{HEATMAP_TOOLTIP_NORM}: {format_duration_short(metrics['max_work_seconds'])}\n"
            f"{HEATMAP_TOOLTIP_PERCENT}: {pct_str}"
        )

    def _cell_clickable(self, date: datetime.date) -> bool:
        # Кликабельны только дни с данными — открывают дневной отчёт.
        return self._metrics(date) is not None

    def _on_cell_click(self, date: datetime.date):
        ReportViewer(self.win, filepath=get_report_path(date))

    def _build_legend(self):
        legend = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        legend.pack(pady=(4, 4))

        items = [
            (theme.COLOR_GREEN, HEATMAP_LEGEND_HIGH.format(threshold=RECOMMENDED_ACTIVITY_THRESHOLD)),
            (theme.COLOR_YELLOW, HEATMAP_LEGEND_MID.format(
                min=MIN_ACTIVITY_THRESHOLD, max=RECOMMENDED_ACTIVITY_THRESHOLD,
            )),
            (theme.COLOR_RED, HEATMAP_LEGEND_LOW.format(threshold=MIN_ACTIVITY_THRESHOLD)),
            (theme.COLOR_GRAY, HEATMAP_LEGEND_NO_DATA),
        ]
        for color, label in items:
            self._legend_item(legend, color, label)

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
