"""
Окно отчёта за период: основные итоги + детализация по дням.
"""

import datetime
import tkinter as tk
from tkinter import ttk

from config import MAIN_FONT_SIZE, MIN_ACTIVITY_THRESHOLD, RECOMMENDED_ACTIVITY_THRESHOLD
from constants import (
    COLOR_DARK_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_LIGHT_FG,
    COLOR_MUTED,
    COLOR_RED,
    COLOR_WHITE,
    COLOR_YELLOW,
    FONT_FAMILY,
    PERIOD_REPORT_BREAKDOWN_LABEL,
    PERIOD_REPORT_CLOSE,
    PERIOD_REPORT_COL_ACTIVE,
    PERIOD_REPORT_COL_ACTIVE_PCT,
    PERIOD_REPORT_COL_DATE,
    PERIOD_REPORT_COL_MAX,
    PERIOD_REPORT_COL_WORK,
    PERIOD_REPORT_COL_WORK_PCT,
    PERIOD_REPORT_DEFICIT_ACTIVE,
    PERIOD_REPORT_DEFICIT_WORK,
    PERIOD_REPORT_NO_NORM,
    PERIOD_REPORT_PERIOD_LABEL,
    PERIOD_REPORT_TOTAL_ACTIVE,
    PERIOD_REPORT_TOTAL_MAX_WORK,
    PERIOD_REPORT_TOTAL_WORK,
    PERIOD_REPORT_TOTALS_LABEL,
    PERIOD_REPORT_WINDOW_TITLE,
)
from modules.period_report import percent
from modules.ui_utils import center_on_screen
from utility import format_date_display, format_duration_short

# Теги Treeview для цветовой подсветки строк
_TAG_HIGH = "activity_high"
_TAG_MID = "activity_mid"
_TAG_LOW = "activity_low"
_TAG_DAY_OFF = "day_off"


def _activity_tag(active_pct: float | None) -> str:
    """Тег строки по дневному % активности (None → нерабочий день)."""
    if active_pct is None:
        return _TAG_DAY_OFF
    if active_pct >= RECOMMENDED_ACTIVITY_THRESHOLD:
        return _TAG_HIGH
    if active_pct >= MIN_ACTIVITY_THRESHOLD:
        return _TAG_MID
    return _TAG_LOW


def _patch_treeview_tag_colors():
    """Обходит баг ttk, из-за которого Treeview игнорирует цвета тегов в темах
    с тяжёлой стилизацией (Windows: vista/xpnative). Вызывать один раз на стиль.
    """
    style = ttk.Style()

    def fixed_map(option):
        return [
            elm for elm in style.map("Treeview", query_opt=option)
            if elm[:2] != ("!disabled", "!selected")
        ]

    style.map(
        "Treeview",
        foreground=fixed_map("foreground"),
        background=fixed_map("background"),
    )


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return PERIOD_REPORT_NO_NORM
    return f"{value:.1f}%"


class PeriodReportViewer:
    """Окно отчёта за период."""

    def __init__(
        self,
        parent: tk.Misc,
        start: datetime.date,
        end: datetime.date,
        report: dict,
    ):
        self.win = tk.Toplevel(parent)
        self.win.title(PERIOD_REPORT_WINDOW_TITLE)
        self.win.transient(parent)
        self.win.configure(bg=COLOR_DARK_BG)
        self.win.resizable(False, False)

        self._render(start, end, report)
        center_on_screen(self.win)

    def _render(self, start: datetime.date, end: datetime.date, report: dict):
        totals = report["totals"]
        days = report["days"]

        # --- Период ---
        header_frame = tk.Frame(self.win, bg=COLOR_DARK_BG, padx=16, pady=8)
        header_frame.pack(fill=tk.X, pady=(12, 4))
        period_text = f"{format_date_display(start)} — {format_date_display(end)}"
        self._stat_row(header_frame, PERIOD_REPORT_PERIOD_LABEL, period_text)

        # --- Итоги за период ---
        section_label = tk.Label(
            self.win, text=PERIOD_REPORT_TOTALS_LABEL,
            bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"), anchor=tk.W,
        )
        section_label.pack(fill=tk.X, padx=16, pady=(8, 4))

        totals_frame = tk.Frame(self.win, bg=COLOR_DARK_BG, padx=16, pady=4)
        totals_frame.pack(fill=tk.X)

        max_work = totals["max_work_seconds"]
        active_pct = percent(totals["active_seconds"], max_work)
        work_pct = percent(totals["total_work_seconds"], max_work)

        recommended_active = int(max_work * RECOMMENDED_ACTIVITY_THRESHOLD / 100)
        active_deficit = max(0, recommended_active - totals["active_seconds"])
        work_deficit = max(0, max_work - totals["total_work_seconds"])

        self._stat_row(
            totals_frame, PERIOD_REPORT_TOTAL_ACTIVE,
            f"{format_duration_short(totals['active_seconds'])}  ({_fmt_pct(active_pct)})",
        )
        self._stat_row(
            totals_frame, PERIOD_REPORT_TOTAL_WORK,
            f"{format_duration_short(totals['total_work_seconds'])}  ({_fmt_pct(work_pct)})",
        )
        self._stat_row(
            totals_frame, PERIOD_REPORT_TOTAL_MAX_WORK,
            format_duration_short(max_work),
        )
        self._stat_row(
            totals_frame, PERIOD_REPORT_DEFICIT_ACTIVE,
            format_duration_short(active_deficit),
        )
        self._stat_row(
            totals_frame, PERIOD_REPORT_DEFICIT_WORK,
            format_duration_short(work_deficit),
        )

        # --- Разделитель ---
        tk.Frame(self.win, bg=COLOR_MUTED, height=1).pack(fill=tk.X, padx=16, pady=(8, 0))

        # --- По дням ---
        breakdown_label = tk.Label(
            self.win, text=PERIOD_REPORT_BREAKDOWN_LABEL,
            bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"), anchor=tk.W,
        )
        breakdown_label.pack(fill=tk.X, padx=16, pady=(8, 4))

        self._build_breakdown_table(days)

        # --- Закрыть ---
        tk.Button(
            self.win, text=PERIOD_REPORT_CLOSE, command=self.win.destroy,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(pady=(8, 12))

    def _stat_row(self, parent: tk.Frame, label: str, value: str):
        row = tk.Frame(parent, bg=COLOR_DARK_BG)
        row.pack(fill=tk.X, pady=1)
        tk.Label(
            row, text=f"{label}:", bg=COLOR_DARK_BG, fg=COLOR_MUTED,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Label(
            row, text=value, bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"), anchor=tk.E,
        ).pack(side=tk.RIGHT)

    def _build_breakdown_table(self, days: list[dict]):
        container = tk.Frame(self.win, bg=COLOR_DARK_BG, padx=16, pady=4)
        container.pack(fill=tk.BOTH, expand=True)

        _patch_treeview_tag_colors()

        columns = ("date", "active", "active_pct", "work", "work_pct", "max")
        tree = ttk.Treeview(
            container, columns=columns, show="headings",
            height=min(15, max(3, len(days))),
        )

        # Цветовая подсветка строк по дневному % активности
        tree.tag_configure(_TAG_HIGH, background=COLOR_GREEN, foreground=COLOR_WHITE)
        tree.tag_configure(_TAG_MID, background=COLOR_YELLOW, foreground=COLOR_WHITE)
        tree.tag_configure(_TAG_LOW, background=COLOR_RED, foreground=COLOR_WHITE)
        tree.tag_configure(_TAG_DAY_OFF, background=COLOR_GRAY, foreground=COLOR_WHITE)

        headings = {
            "date": PERIOD_REPORT_COL_DATE,
            "active": PERIOD_REPORT_COL_ACTIVE,
            "active_pct": PERIOD_REPORT_COL_ACTIVE_PCT,
            "work": PERIOD_REPORT_COL_WORK,
            "work_pct": PERIOD_REPORT_COL_WORK_PCT,
            "max": PERIOD_REPORT_COL_MAX,
        }
        widths = {
            "date": 100,
            "active": 100,
            "active_pct": 70,
            "work": 100,
            "work_pct": 70,
            "max": 100,
        }
        for col in columns:
            tree.heading(col, text=headings[col])
            anchor = tk.W if col == "date" else tk.CENTER
            tree.column(col, width=widths[col], anchor=anchor, stretch=False)

        for d in days:
            max_s = d["max_work_seconds"]
            active_p = percent(d["active_seconds"], max_s)
            work_p = percent(d["total_work_seconds"], max_s)
            tree.insert(
                "", tk.END,
                values=(
                    format_date_display(d["date"]),
                    format_duration_short(d["active_seconds"]),
                    _fmt_pct(active_p),
                    format_duration_short(d["total_work_seconds"]),
                    _fmt_pct(work_p),
                    format_duration_short(max_s),
                ),
                tags=(_activity_tag(active_p),),
            )

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
