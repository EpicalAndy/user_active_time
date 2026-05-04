"""
Диалог ручного управления активным временем
"""

import tkinter as tk
from tkinter import ttk

from config import MAIN_FONT_SIZE
from constants import (
    COLOR_MUTED,
    COLOR_RED,
    DEFAULT_MANUAL_ACTIVITY_DESCRIPTION,
    FONT_FAMILY,
)
from modules.session_monitor import (
    add_manual_active_time,
    get_manual_active_entries,
    remove_manual_active_time,
)
from modules.ui_utils import center_on_parent


class ManualActivityDialog:
    """Модальное окно для добавления и удаления ручного активного времени"""

    def __init__(self, parent: tk.Misc, date_key: str):
        self.date_key = date_key
        self.changed = False
        self._entry_vars: list[tuple[tk.BooleanVar, dict]] = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Добавить активное время")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._create_widgets()
        self._refresh_entries()
        self._update_confirm_state()
        center_on_parent(self.dialog, parent)
        self.dialog.focus_set()

    def _create_widgets(self):
        # === Блок «Добавить диапазон» ===
        add_frame = ttk.LabelFrame(self.dialog, text="Добавить диапазон")
        add_frame.pack(fill=tk.X, padx=10, pady=(8, 4))

        # --- Время "С" ---
        from_frame = tk.Frame(add_frame)
        from_frame.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(from_frame, text="С:", width=4, anchor=tk.W,
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT)
        self._from_hour = tk.StringVar()
        self._from_minute = tk.StringVar()
        self._add_time_widgets(from_frame, self._from_hour, self._from_minute)

        # --- Время "По" ---
        to_frame = tk.Frame(add_frame)
        to_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(to_frame, text="По:", width=4, anchor=tk.W,
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT)
        self._to_hour = tk.StringVar()
        self._to_minute = tk.StringVar()
        self._add_time_widgets(to_frame, self._to_hour, self._to_minute)

        # --- Описание ---
        desc_frame = tk.Frame(add_frame)
        desc_frame.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(desc_frame, text="Описание:", anchor=tk.W,
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(anchor=tk.W)
        self._desc_entry = tk.Entry(desc_frame, font=(FONT_FAMILY, MAIN_FONT_SIZE))
        self._desc_entry.pack(fill=tk.X, pady=(2, 0))

        # --- Сообщение об ошибке валидации ---
        self._error_label = tk.Label(
            add_frame, text="", fg=COLOR_RED,
            font=(FONT_FAMILY, 9), anchor=tk.W,
        )
        self._error_label.pack(fill=tk.X, padx=8, pady=(2, 0))

        # --- Кнопка "Подтвердить" ---
        confirm_frame = tk.Frame(add_frame)
        confirm_frame.pack(fill=tk.X, padx=8, pady=(4, 8))
        self._confirm_btn = ttk.Button(
            confirm_frame, text="Подтвердить", command=self._confirm,
        )
        self._confirm_btn.pack(side=tk.RIGHT)

        for var in (self._from_hour, self._from_minute, self._to_hour, self._to_minute):
            var.trace_add("write", lambda *_: self._update_confirm_state())

        # === Блок «Добавленные диапазоны» ===
        list_frame = ttk.LabelFrame(self.dialog, text="Добавленные диапазоны")
        list_frame.pack(fill=tk.X, padx=10, pady=(4, 10))

        self._entries_frame = tk.Frame(list_frame)
        self._entries_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        del_frame = tk.Frame(list_frame)
        del_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._delete_btn = ttk.Button(
            del_frame, text="Удалить", command=self._delete_selected,
        )
        self._delete_btn.pack(side=tk.RIGHT)

    def _add_time_widgets(self, parent: tk.Frame, hour_var: tk.StringVar, minute_var: tk.StringVar):
        ttk.Spinbox(
            parent, from_=0, to=23, width=4, textvariable=hour_var,
            format="%02.0f", justify=tk.CENTER,
        ).pack(side=tk.LEFT)
        tk.Label(parent, text="часы",
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Spinbox(
            parent, from_=0, to=59, width=4, textvariable=minute_var,
            format="%02.0f", justify=tk.CENTER,
        ).pack(side=tk.LEFT)
        tk.Label(parent, text="минуты",
                 font=(FONT_FAMILY, MAIN_FONT_SIZE)).pack(side=tk.LEFT, padx=(4, 0))

    def _refresh_entries(self):
        """Перерисовывает список добавленных диапазонов из state.json"""
        for widget in self._entries_frame.winfo_children():
            widget.destroy()
        self._entry_vars = []

        entries = get_manual_active_entries(self.date_key)
        if not entries:
            tk.Label(
                self._entries_frame, text="Нет добавленных диапазонов",
                fg=COLOR_MUTED, font=(FONT_FAMILY, MAIN_FONT_SIZE),
                anchor=tk.W,
            ).pack(fill=tk.X, padx=4, pady=4)
        else:
            for entry in entries:
                var = tk.BooleanVar(value=False)
                row = tk.Frame(self._entries_frame)
                row.pack(fill=tk.X, padx=2, pady=1)
                tk.Checkbutton(
                    row, variable=var,
                    command=self._update_delete_btn_state,
                ).pack(side=tk.LEFT)
                text = f"{entry['start'][:5]}—{entry['end'][:5]}  {entry['description']}"
                tk.Label(
                    row, text=text, anchor=tk.W,
                    font=(FONT_FAMILY, MAIN_FONT_SIZE),
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)
                self._entry_vars.append((var, entry))

        self._update_delete_btn_state()
        self.dialog.update_idletasks()

    def _update_delete_btn_state(self):
        any_selected = any(var.get() for var, _ in self._entry_vars)
        self._delete_btn.configure(state=tk.NORMAL if any_selected else tk.DISABLED)

    def _delete_selected(self):
        to_delete = [entry for var, entry in self._entry_vars if var.get()]
        for entry in to_delete:
            if remove_manual_active_time(
                self.date_key, entry["start"], entry["end"], entry["description"],
            ):
                self.changed = True
        self._refresh_entries()

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

    def _update_confirm_state(self):
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

        add_manual_active_time(self.date_key, from_str, to_str, desc)
        self.changed = True

        self._from_hour.set("")
        self._from_minute.set("")
        self._to_hour.set("")
        self._to_minute.set("")
        self._desc_entry.delete(0, tk.END)
        self._refresh_entries()

    def _cancel(self):
        self.dialog.destroy()

    def wait(self):
        """Блокирует до закрытия диалога"""
        self.dialog.wait_window()
