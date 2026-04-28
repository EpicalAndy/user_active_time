"""
Модальный диалог выбора периода для построения отчёта.
"""

import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from config import MAIN_FONT_SIZE
from constants import (
    COLOR_RED,
    FONT_FAMILY,
    PERIOD_DIALOG_BUILD_BUTTON,
    PERIOD_DIALOG_CALENDAR_BUTTON,
    PERIOD_DIALOG_DATE_PLACEHOLDER,
    PERIOD_DIALOG_ERROR_INVALID,
    PERIOD_DIALOG_ERROR_NO_DATA_TEMPLATE,
    PERIOD_DIALOG_ERROR_NO_DATA_TITLE,
    PERIOD_DIALOG_ERROR_RANGE,
    PERIOD_DIALOG_ERROR_SAME_DAY,
    PERIOD_DIALOG_FROM_LABEL,
    PERIOD_DIALOG_TITLE,
    PERIOD_DIALOG_TO_LABEL,
)
from modules.calendar_popup import CalendarPopup
from modules.period_report import build_period_report
from modules.period_report_viewer import PeriodReportViewer
from utility import format_date_display

_DATE_FMT = "%d.%m.%Y"


class PeriodReportDialog:
    """Диалог выбора дат периода и запуска построения отчёта."""

    def __init__(self, parent: tk.Misc):
        self._parent = parent

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(PERIOD_DIALOG_TITLE)
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._from_var = tk.StringVar()
        self._to_var = tk.StringVar()

        self._create_widgets()
        self._update_state()
        self._center_on_parent(parent)
        self.dialog.focus_set()

    def _center_on_parent(self, parent: tk.Misc):
        self.dialog.update_idletasks()
        dw = self.dialog.winfo_width()
        dh = self.dialog.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        x = max(0, min(x, sw - dw))
        y = max(0, min(y, sh - dh))
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        pad = {"padx": 12, "pady": 6}

        self._build_date_row(
            label=PERIOD_DIALOG_FROM_LABEL, var=self._from_var, pad=pad,
        )
        self._build_date_row(
            label=PERIOD_DIALOG_TO_LABEL, var=self._to_var, pad=pad,
        )

        self._error_label = tk.Label(
            self.dialog, text="", fg=COLOR_RED,
            font=(FONT_FAMILY, 9), anchor=tk.W,
        )
        self._error_label.pack(fill=tk.X, padx=12, pady=(0, 2))

        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=12, pady=(4, 12))
        self._build_btn = ttk.Button(
            btn_frame, text=PERIOD_DIALOG_BUILD_BUTTON, command=self._build,
        )
        self._build_btn.pack(side=tk.RIGHT)

        for var in (self._from_var, self._to_var):
            var.trace_add("write", lambda *_: self._update_state())

    def _build_date_row(self, label: str, var: tk.StringVar, pad: dict):
        row = tk.Frame(self.dialog)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text=label, width=4, anchor=tk.W,
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT)
        tk.Entry(
            row, textvariable=var, width=14,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), justify=tk.CENTER,
        ).pack(side=tk.LEFT)
        ttk.Button(
            row, text=PERIOD_DIALOG_CALENDAR_BUTTON, width=3,
            command=lambda: self._open_calendar(var),
        ).pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(row, text=f"  ({PERIOD_DIALOG_DATE_PLACEHOLDER})",
                 font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)

    def _open_calendar(self, target_var: tk.StringVar):
        initial = self._parse_date(target_var.get())
        CalendarPopup(
            self.dialog,
            on_select=lambda d: target_var.set(format_date_display(d)),
            initial_date=initial,
        )

    def _parse_date(self, s: str) -> datetime.date | None:
        s = s.strip()
        if not s:
            return None
        try:
            return datetime.datetime.strptime(s, _DATE_FMT).date()
        except ValueError:
            return None

    def _update_state(self):
        from_raw = self._from_var.get().strip()
        to_raw = self._to_var.get().strip()
        from_date = self._parse_date(from_raw)
        to_date = self._parse_date(to_raw)

        if not from_raw or not to_raw:
            self._error_label.configure(text="")
            self._build_btn.configure(state=tk.DISABLED)
            return

        if from_date is None or to_date is None:
            self._error_label.configure(text=PERIOD_DIALOG_ERROR_INVALID)
            self._build_btn.configure(state=tk.DISABLED)
            return

        if from_date == to_date:
            self._error_label.configure(text=PERIOD_DIALOG_ERROR_SAME_DAY)
            self._build_btn.configure(state=tk.DISABLED)
            return

        if from_date > to_date:
            self._error_label.configure(text=PERIOD_DIALOG_ERROR_RANGE)
            self._build_btn.configure(state=tk.DISABLED)
            return

        self._error_label.configure(text="")
        self._build_btn.configure(state=tk.NORMAL)

    def _build(self):
        from_date = self._parse_date(self._from_var.get())
        to_date = self._parse_date(self._to_var.get())
        if from_date is None or to_date is None:
            return

        report = build_period_report(from_date, to_date)
        if report["missing_boundary"]:
            dates = ", ".join(format_date_display(d) for d in report["missing_boundary"])
            messagebox.showerror(
                PERIOD_DIALOG_ERROR_NO_DATA_TITLE,
                PERIOD_DIALOG_ERROR_NO_DATA_TEMPLATE.format(dates=dates),
                parent=self.dialog,
            )
            return

        parent = self._parent
        self.dialog.destroy()
        PeriodReportViewer(parent, from_date, to_date, report)

    def _cancel(self):
        self.dialog.destroy()

    def wait(self):
        self.dialog.wait_window()
