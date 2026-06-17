"""
Диалог настройки одного дня календаря рабочего времени.

Позволяет для конкретной даты выбрать режим лимита и задать заметку:
    «По расписанию» — переопределения нет (действует расписание по дню недели)
    «Свой лимит»    — задать число часов вручную
    «Выходной»      — лимит 0, день не отслеживается
Запись сохраняется в modules.work_calendar.
"""

import datetime
import tkinter as tk
from collections.abc import Callable

import utility
from config import MAIN_FONT_SIZE
from constants import (
    DAY_DIALOG_CANCEL,
    DAY_DIALOG_DAYOFF,
    DAY_DIALOG_HOURS_LABEL,
    DAY_DIALOG_NOTE_LABEL,
    DAY_DIALOG_SAVE,
    DAY_DIALOG_TITLE,
    DAY_DIALOG_USE_SCHEDULE,
    FONT_FAMILY,
)
from modules import theme, work_calendar
from modules.ui_utils import center_on_parent
from utility import format_date_display

_MODE_SCHEDULE = "schedule"
_MODE_LIMIT = "limit"
_MODE_DAYOFF = "dayoff"


class DayScheduleDialog:
    """Модальный диалог настройки лимита и заметки для одной даты."""

    def __init__(
        self,
        parent: tk.Misc,
        date: datetime.date,
        on_saved: Callable[[], None] | None = None,
    ):
        self.date = date
        self.on_saved = on_saved

        self.win = tk.Toplevel(parent)
        self.win.title(f"{DAY_DIALOG_TITLE} — {format_date_display(date)}")
        self.win.transient(parent.winfo_toplevel())
        self.win.configure(bg=theme.COLOR_DARK_BG)
        self.win.resizable(False, False)
        self.win.grab_set()
        # Восстанавливаем grab родителя при закрытии, чтобы календарь
        # снова реагировал на клики (см. CalendarPopup._on_destroy).
        self.win.bind("<Destroy>", self._on_destroy)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

        self._mode_var = tk.StringVar()
        self._hours_var = tk.DoubleVar()

        self._build_ui()
        self._load_state()
        center_on_parent(self.win, parent)

    def _build_ui(self):
        pad = {"padx": 16, "pady": 4}

        # --- Режим лимита ---
        sched_row = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        sched_row.pack(fill=tk.X, anchor=tk.W, **pad)
        tk.Radiobutton(
            sched_row, text=DAY_DIALOG_USE_SCHEDULE,
            variable=self._mode_var, value=_MODE_SCHEDULE,
            command=self._update_hours_state,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            selectcolor=theme.COLOR_DARKER_BG, activebackground=theme.COLOR_DARK_BG,
            activeforeground=theme.COLOR_LIGHT_FG, anchor=tk.W,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.LEFT)

        limit_row = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        limit_row.pack(fill=tk.X, anchor=tk.W, **pad)
        tk.Radiobutton(
            limit_row, text=DAY_DIALOG_HOURS_LABEL,
            variable=self._mode_var, value=_MODE_LIMIT,
            command=self._update_hours_state,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            selectcolor=theme.COLOR_DARKER_BG, activebackground=theme.COLOR_DARK_BG,
            activeforeground=theme.COLOR_LIGHT_FG, anchor=tk.W,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.LEFT)
        self._hours_spin = tk.Spinbox(
            limit_row, from_=0, to=24, increment=0.25, width=6,
            textvariable=self._hours_var, justify=tk.CENTER, format="%.2f",
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        )
        self._hours_spin.pack(side=tk.LEFT, padx=(8, 0))

        dayoff_row = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        dayoff_row.pack(fill=tk.X, anchor=tk.W, **pad)
        tk.Radiobutton(
            dayoff_row, text=DAY_DIALOG_DAYOFF,
            variable=self._mode_var, value=_MODE_DAYOFF,
            command=self._update_hours_state,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            selectcolor=theme.COLOR_DARKER_BG, activebackground=theme.COLOR_DARK_BG,
            activeforeground=theme.COLOR_LIGHT_FG, anchor=tk.W,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.LEFT)

        # --- Заметка ---
        tk.Label(
            self.win, text=DAY_DIALOG_NOTE_LABEL,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG, anchor=tk.W,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(fill=tk.X, padx=16, pady=(10, 2))
        self._note_text = tk.Text(
            self.win, height=3, width=32, wrap=tk.WORD,
            bg=theme.COLOR_DARKER_BG, fg=theme.COLOR_LIGHT_FG,
            insertbackground=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), relief=tk.FLAT,
        )
        self._note_text.pack(padx=16, pady=(0, 8))

        # --- Кнопки ---
        btn_row = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        btn_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        tk.Button(
            btn_row, text=DAY_DIALOG_SAVE, command=self._save,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.RIGHT)
        tk.Button(
            btn_row, text=DAY_DIALOG_CANCEL, command=self.win.destroy,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _load_state(self):
        override = work_calendar.get_override_hours(self.date)
        if override is None:
            self._mode_var.set(_MODE_SCHEDULE)
            # Предзаполняем спинбокс значением по расписанию как отправную точку.
            self._hours_var.set(round(utility.get_work_hours(self.date), 2))
        elif override == 0:
            self._mode_var.set(_MODE_DAYOFF)
            self._hours_var.set(0.0)
        else:
            self._mode_var.set(_MODE_LIMIT)
            self._hours_var.set(round(override, 2))

        note = work_calendar.get_note(self.date)
        if note:
            self._note_text.insert("1.0", note)
        self._update_hours_state()

    def _update_hours_state(self):
        """Спинбокс активен только в режиме «Свой лимит»."""
        state = tk.NORMAL if self._mode_var.get() == _MODE_LIMIT else tk.DISABLED
        self._hours_spin.configure(state=state)

    def _save(self):
        mode = self._mode_var.get()
        if mode == _MODE_SCHEDULE:
            hours = None
        elif mode == _MODE_DAYOFF:
            hours = 0.0
        else:
            try:
                hours = float(self._hours_var.get())
            except (tk.TclError, ValueError):
                hours = 0.0
            # Нулевой «свой лимит» эквивалентен выходному.
            hours = max(0.0, hours)

        note = self._note_text.get("1.0", tk.END).strip()
        work_calendar.set_entry(self.date, hours, note)

        if self.on_saved is not None:
            self.on_saved()
        self.win.destroy()

    def _on_destroy(self, event: tk.Event):
        if event.widget is not self.win:
            return
        try:
            parent = self.win.master
            if isinstance(parent, (tk.Toplevel, tk.Tk)):
                parent.grab_set()
        except tk.TclError:
            pass
