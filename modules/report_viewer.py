"""
Визуализация отчёта об активности — окно со статистикой и графиком активности/простоя
"""

import datetime
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

from config import LOG_DIR, MAIN_FONT_SIZE

# Цвета
_BG = "#2C3E50"
_FG = "#ECF0F1"
_CHART_ACTIVE = "#27AE60"
_CHART_INACTIVE = "#E74C3C"
_CHART_BG = "#BDC3C7"
_CHART_GRID = "#95A5A6"
_STAT_LABEL_FG = "#95A5A6"

# Типы событий → активность
_ACTIVE_EVENTS = {"LOGON", "UNLOCK", "INPUT_ACTIVE", "MONITOR_START"}
_INACTIVE_EVENTS = {"LOGOFF", "LOCK", "INPUT_INACTIVE", "MONITOR_STOP"}

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*\S+\s*\|\s*(\S+)"
)


def _parse_report(filepath: str) -> dict | None:
    """Парсит файл отчёта. Возвращает dict с данными или None если невалидный."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    # Проверяем обязательные маркеры
    if "Пользователь:" not in text or "Лог активности:" not in text:
        return None

    result = {}

    # Парсим заголовок
    for line in text.splitlines():
        if line.startswith("Пользователь:"):
            result["user"] = line.split(":", 1)[1].strip()
        elif line.startswith("Дата:"):
            result["date"] = line.split(":", 1)[1].strip()
        elif line.startswith("Общее активное время:"):
            result["active_time"] = line.split(":", 1)[1].strip()
        elif line.startswith("Максимальное рабочее время:"):
            result["max_work_time"] = line.split(":", 1)[1].strip()
        elif line.startswith("Общее время работы:"):
            result["total_work_time"] = line.split(":", 1)[1].strip()
        elif line.startswith("Количество активных сессий:"):
            result["session_count"] = line.split(":", 1)[1].strip()
        elif line.startswith("Процент активности:"):
            result["activity_percent"] = line.split(":", 1)[1].strip()

    if "date" not in result:
        return None

    # Парсим лог-записи
    log_section = text.split("Лог активности:", 1)
    if len(log_section) < 2:
        return None

    events = []
    for line in log_section[1].strip().splitlines():
        m = _LOG_LINE_RE.match(line.strip())
        if m:
            ts_str, event_type = m.group(1), m.group(2)
            try:
                ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            events.append((ts, event_type))

    result["events"] = events
    return result


def _build_intervals(events: list[tuple[datetime.datetime, str]]) -> list[tuple[float, float, bool]]:
    """
    Строит интервалы активности/простоя из событий.
    Возвращает список (start_hour, end_hour, is_active).
    """
    if not events:
        return []

    intervals = []
    is_active = True  # После первого события (MONITOR_START/LOGON) считаем активным
    prev_hour = _time_to_hours(events[0][0])

    for ts, event_type in events:
        hour = _time_to_hours(ts)

        if hour > prev_hour:
            intervals.append((prev_hour, hour, is_active))

        if event_type in _ACTIVE_EVENTS:
            is_active = True
        elif event_type in _INACTIVE_EVENTS:
            is_active = False

        prev_hour = hour

    # Последний интервал до последнего события (уже добавлен)
    return intervals


def _time_to_hours(dt: datetime.datetime) -> float:
    """Переводит время в дробные часы (0.0 — 24.0)"""
    return dt.hour + dt.minute / 60 + dt.second / 3600


class ReportViewer:
    """Окно визуализации отчёта"""

    def __init__(self, parent: tk.Misc):
        filepath = filedialog.askopenfilename(
            parent=parent,
            title="Выберите файл отчёта",
            initialdir=LOG_DIR,
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
        )

        if not filepath:
            return

        data = _parse_report(filepath)
        if data is None:
            messagebox.showerror(
                "Ошибка",
                "Выбранный файл не является отчётом об активности.\n\n"
                "Файл должен содержать строки «Пользователь:», «Дата:» "
                "и раздел «Лог активности:».",
                parent=parent,
            )
            return

        self._show_window(parent, data, os.path.basename(filepath))

    def _show_window(self, parent: tk.Misc, data: dict, filename: str):
        self.win = tk.Toplevel(parent)
        self.win.title(f"Отчёт — {data.get('date', filename)}")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.configure(bg=_BG)

        # --- Статистика ---
        stats_frame = tk.Frame(self.win, bg=_BG, padx=16, pady=12)
        stats_frame.pack(fill=tk.X)

        stats = [
            ("Пользователь", data.get("user", "—")),
            ("Дата", data.get("date", "—")),
            ("Активное время", data.get("active_time", "—")),
            ("Рабочее время", data.get("total_work_time", "—")),
            ("Макс. рабочее время", data.get("max_work_time", "—")),
            ("Сессий", data.get("session_count", "—")),
            ("Активность", data.get("activity_percent", "—")),
        ]

        for label_text, value_text in stats:
            row = tk.Frame(stats_frame, bg=_BG)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row, text=f"{label_text}:", bg=_BG, fg=_STAT_LABEL_FG,
                font=("Segoe UI", MAIN_FONT_SIZE), anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=value_text, bg=_BG, fg=_FG,
                font=("Segoe UI", MAIN_FONT_SIZE, "bold"), anchor=tk.E,
            ).pack(side=tk.RIGHT)

        # --- Разделитель ---
        tk.Frame(self.win, bg=_CHART_GRID, height=1).pack(fill=tk.X, padx=16)

        # --- График ---
        chart_label = tk.Label(
            self.win, text="Активность за день", bg=_BG, fg=_FG,
            font=("Segoe UI", MAIN_FONT_SIZE, "bold"),
        )
        chart_label.pack(pady=(10, 4))

        self._draw_chart(data)

        # --- Легенда ---
        legend_frame = tk.Frame(self.win, bg=_BG)
        legend_frame.pack(pady=(4, 12))

        self._legend_item(legend_frame, _CHART_ACTIVE, "Активность")
        self._legend_item(legend_frame, _CHART_INACTIVE, "Простой")

        # --- Кнопка закрыть ---
        tk.Button(
            self.win, text="Закрыть", command=self.win.destroy,
            font=("Segoe UI", MAIN_FONT_SIZE - 1),
        ).pack(pady=(0, 12))

        # Центрируем окно на экране
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _draw_chart(self, data: dict):
        """Рисует столбчатый график активности на Canvas"""
        events = data.get("events", [])
        intervals = _build_intervals(events)

        chart_width = 560
        chart_height = 40
        pad_left = 30
        pad_right = 16
        pad_top = 8
        pad_bottom = 24

        canvas_w = pad_left + chart_width + pad_right
        canvas_h = pad_top + chart_height + pad_bottom

        canvas = tk.Canvas(
            self.win, width=canvas_w, height=canvas_h,
            bg=_BG, highlightthickness=0,
        )
        canvas.pack(padx=16, pady=4)

        # Определяем диапазон часов
        if intervals:
            min_hour = max(0, int(intervals[0][0]))
            max_hour = min(24, int(intervals[-1][1]) + 1)
        elif events:
            first_h = int(_time_to_hours(events[0][0]))
            last_h = int(_time_to_hours(events[-1][0])) + 1
            min_hour = max(0, first_h)
            max_hour = min(24, last_h)
        else:
            min_hour, max_hour = 0, 24

        if max_hour <= min_hour:
            max_hour = min_hour + 1

        hour_span = max_hour - min_hour

        def hour_to_x(h: float) -> float:
            return pad_left + (h - min_hour) / hour_span * chart_width

        # Фон графика
        canvas.create_rectangle(
            pad_left, pad_top,
            pad_left + chart_width, pad_top + chart_height,
            fill=_CHART_BG, outline="",
        )

        # Интервалы активности/простоя
        for start_h, end_h, is_active in intervals:
            x1 = hour_to_x(max(start_h, min_hour))
            x2 = hour_to_x(min(end_h, max_hour))
            color = _CHART_ACTIVE if is_active else _CHART_INACTIVE
            canvas.create_rectangle(
                x1, pad_top, x2, pad_top + chart_height,
                fill=color, outline="",
            )

        # Сетка и подписи часов
        for h in range(min_hour, max_hour + 1):
            x = hour_to_x(h)
            # Вертикальная линия сетки
            canvas.create_line(
                x, pad_top, x, pad_top + chart_height,
                fill=_CHART_GRID, width=1,
            )
            # Подпись часа
            canvas.create_text(
                x, pad_top + chart_height + 4,
                text=str(h), anchor=tk.N,
                fill=_FG, font=("Segoe UI", 8),
            )

    def _legend_item(self, parent: tk.Frame, color: str, text: str):
        """Добавляет элемент легенды"""
        frame = tk.Frame(parent, bg=_BG)
        frame.pack(side=tk.LEFT, padx=12)

        box = tk.Canvas(frame, width=14, height=14, bg=_BG, highlightthickness=0)
        box.pack(side=tk.LEFT, padx=(0, 4))
        box.create_rectangle(1, 1, 13, 13, fill=color, outline="")

        tk.Label(
            frame, text=text, bg=_BG, fg=_FG,
            font=("Segoe UI", MAIN_FONT_SIZE - 1),
        ).pack(side=tk.LEFT)
