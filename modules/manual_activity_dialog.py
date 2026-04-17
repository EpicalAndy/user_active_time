"""
Диалог ручного добавления активного времени
"""

import tkinter as tk
from tkinter import ttk

from config import MAIN_FONT_SIZE
from constants import (
    COLOR_RED,
    DEFAULT_MANUAL_ACTIVITY_DESCRIPTION,
    FONT_FAMILY,
)


class ManualActivityDialog:
    """Модальное окно для ручного добавления активного времени"""

    def __init__(self, parent: tk.Misc):
        self.result: tuple[str, str, str] | None = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Добавить активное время")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._create_widgets()
        self._update_button_state()
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
        pad = {"padx": 12, "pady": 4}

        # --- Время "С" ---
        from_frame = tk.Frame(self.dialog)
        from_frame.pack(fill=tk.X, **pad)
        tk.Label(from_frame, text="С:", width=10, anchor=tk.W,
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT)

        self._from_hour = tk.StringVar()
        self._from_minute = tk.StringVar()
        self._add_time_widgets(from_frame, self._from_hour, self._from_minute)

        # --- Время "По" ---
        to_frame = tk.Frame(self.dialog)
        to_frame.pack(fill=tk.X, **pad)
        tk.Label(to_frame, text="По:", width=10, anchor=tk.W,
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT)

        self._to_hour = tk.StringVar()
        self._to_minute = tk.StringVar()
        self._add_time_widgets(to_frame, self._to_hour, self._to_minute)

        # --- Описание ---
        desc_frame = tk.Frame(self.dialog)
        desc_frame.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(desc_frame, text="Описание:", anchor=tk.W,
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(anchor=tk.W)
        self._desc_entry = tk.Entry(desc_frame, font=(FONT_FAMILY, MAIN_FONT_SIZE))
        self._desc_entry.pack(fill=tk.X, pady=(2, 0))

        # --- Сообщение об ошибке валидации ---
        self._error_label = tk.Label(
            self.dialog, text="", fg=COLOR_RED,
            font=(FONT_FAMILY, 9), anchor=tk.W,
        )
        self._error_label.pack(fill=tk.X, padx=12, pady=(2, 0))

        # --- Кнопка "Подтвердить" ---
        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=12, pady=(4, 12))
        self._confirm_btn = ttk.Button(
            btn_frame, text="Подтвердить", command=self._confirm,
        )
        self._confirm_btn.pack(side=tk.RIGHT)

        # Трассируем изменения для включения/отключения кнопки
        for var in (self._from_hour, self._from_minute, self._to_hour, self._to_minute):
            var.trace_add("write", lambda *_: self._update_button_state())

    def _add_time_widgets(self, parent: tk.Frame, hour_var: tk.StringVar, minute_var: tk.StringVar):
        ttk.Spinbox(
            parent, from_=0, to=23, width=4, textvariable=hour_var,
            format="%02.0f", justify=tk.CENTER,
        ).pack(side=tk.LEFT)
        tk.Label(parent, text=":", font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT, padx=2)
        ttk.Spinbox(
            parent, from_=0, to=59, width=4, textvariable=minute_var,
            format="%02.0f", justify=tk.CENTER,
        ).pack(side=tk.LEFT)

    def _parse_minutes(self, hour_var: tk.StringVar, minute_var: tk.StringVar) -> int | None:
        h_str = hour_var.get().strip()
        m_str = minute_var.get().strip()
        if not h_str or not m_str:
            return None
        try:
            h = int(h_str)
            m = int(m_str)
        except ValueError:
            return None
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return h * 60 + m

    def _update_button_state(self):
        from_mins = self._parse_minutes(self._from_hour, self._from_minute)
        to_mins = self._parse_minutes(self._to_hour, self._to_minute)

        if from_mins is None or to_mins is None:
            self._confirm_btn.configure(state=tk.DISABLED)
            self._error_label.configure(text="")
            return

        if to_mins <= from_mins:
            self._confirm_btn.configure(state=tk.DISABLED)
            self._error_label.configure(text="Поле «По» должно быть больше поля «С»")
            return

        self._confirm_btn.configure(state=tk.NORMAL)
        self._error_label.configure(text="")

    def _confirm(self):
        from_h = int(self._from_hour.get())
        from_m = int(self._from_minute.get())
        to_h = int(self._to_hour.get())
        to_m = int(self._to_minute.get())

        desc = self._desc_entry.get().strip() or DEFAULT_MANUAL_ACTIVITY_DESCRIPTION

        from_str = f"{from_h:02d}:{from_m:02d}:00"
        to_str = f"{to_h:02d}:{to_m:02d}:00"

        self.result = (from_str, to_str, desc)
        self.dialog.destroy()

    def _cancel(self):
        self.dialog.destroy()

    def wait(self):
        """Блокирует до закрытия диалога"""
        self.dialog.wait_window()
