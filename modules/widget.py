"""
Виджет отображения активности на рабочем столе
"""

import tkinter as tk
from collections.abc import Callable

from config import (
    MIN_ACTIVITY_THRESHOLD,
    RECOMMENDED_ACTIVITY_THRESHOLD,
    WIDGET_SHOW_ACTIVE_TIME,
    WIDGET_SHOW_ACTIVITY_PERCENT,
    WIDGET_SHOW_SESSION_COUNT,
    WIDGET_UPDATE_INTERVAL,
    MAIN_FONT_SIZE
)
from utility import format_duration

# Цветовая схема
TITLE_BG = "#2C3E50"
TITLE_FG = "#ECF0F1"
CLOSE_HOVER = "#E74C3C"
MINIMIZE_HOVER = "#5D6D7E"
METRIC_FG = "#FFFFFF"

COLOR_GREEN = "#27AE60"
COLOR_YELLOW = "#F39C12"
COLOR_RED = "#E74C3C"


def is_widget_enabled() -> bool:
    """Проверяет, включена ли хотя бы одна опция отображения"""
    return any([
        WIDGET_SHOW_ACTIVE_TIME,
        WIDGET_SHOW_SESSION_COUNT,
        WIDGET_SHOW_ACTIVITY_PERCENT,
    ])


class ActivityWidget:
    """Минималистичный виджет активности на рабочем столе"""

    def __init__(self, stats_provider: Callable[[], dict]):
        self.stats_provider = stats_provider
        self._minimized = False
        self.root = tk.Tk()
        self.root.withdraw()

        self.window = tk.Toplevel(self.root)
        self._setup_window()
        self._create_title_bar()
        self._create_body()
        self._position_window()
        self._schedule_update()

    def _setup_window(self):
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        self.window.configure(bg=TITLE_BG)

    # --- Заголовок ---

    def _create_title_bar(self):
        self._title_frame = tk.Frame(self.window, bg=TITLE_BG, height=30)
        self._title_frame.pack(fill=tk.X)
        self._title_frame.pack_propagate(False)
        title_frame = self._title_frame

        title_label = tk.Label(
            title_frame, text="Активность",
            bg=TITLE_BG, fg=TITLE_FG,
            font=("Segoe UI", MAIN_FONT_SIZE, "bold"), padx=MAIN_FONT_SIZE,
        )
        title_label.pack(side=tk.LEFT, fill=tk.Y)

        close_btn = tk.Label(
            title_frame, text="  \u2715  ",
            bg=TITLE_BG, fg=TITLE_FG,
            font=("Segoe UI", MAIN_FONT_SIZE), cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, fill=tk.Y)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=CLOSE_HOVER))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=TITLE_FG))

        self._minimize_btn = tk.Label(
            title_frame, text="  \u2014  ",
            bg=TITLE_BG, fg=TITLE_FG,
            font=("Segoe UI", MAIN_FONT_SIZE), cursor="hand2",
        )
        self._minimize_btn.pack(side=tk.RIGHT, fill=tk.Y)
        self._minimize_btn.bind("<Button-1>", lambda e: self._toggle_minimize())
        self._minimize_btn.bind("<Enter>", lambda e: self._minimize_btn.configure(fg=MINIMIZE_HOVER))
        self._minimize_btn.bind("<Leave>", lambda e: self._minimize_btn.configure(fg=TITLE_FG))

        # Перетаскивание за заголовок
        for w in (title_frame, title_label):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

    # --- Тело ---

    def _create_body(self):
        self.body_frame = tk.Frame(self.window, bg=COLOR_RED, padx=12, pady=8)
        self.body_frame.pack(fill=tk.BOTH, expand=True)

        self.metric_labels = {}

        if WIDGET_SHOW_ACTIVE_TIME:
            self.metric_labels["active_time"] = self._add_metric("Активное время:")
        if WIDGET_SHOW_SESSION_COUNT:
            self.metric_labels["session_count"] = self._add_metric("Сессий:")
        if WIDGET_SHOW_ACTIVITY_PERCENT:
            self.metric_labels["activity_percent"] = self._add_metric("Активность:")

    def _add_metric(self, label_text: str) -> dict:
        frame = tk.Frame(self.body_frame, bg=COLOR_RED)
        frame.pack(fill=tk.X, pady=2)

        label = tk.Label(
            frame, text=label_text,
            bg=COLOR_RED, fg=METRIC_FG,
            font=("Segoe UI", MAIN_FONT_SIZE), anchor=tk.W,
        )
        label.pack(side=tk.LEFT)

        value = tk.Label(
            frame, text="\u2014",
            bg=COLOR_RED, fg=METRIC_FG,
            font=("Segoe UI", MAIN_FONT_SIZE, "bold"), anchor=tk.E,
        )
        value.pack(side=tk.RIGHT)

        return {"frame": frame, "label": label, "value": value}

    # --- Позиционирование ---

    def _position_window(self):
        self.window.update_idletasks()
        width = 250
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        win_h = self.window.winfo_reqheight()
        x = screen_w - width - 20
        y = screen_h - win_h - 60
        self.window.geometry(f"{width}x{win_h}+{x}+{y}")

    # --- Обновление данных ---

    def _get_body_color(self, activity_percent: float) -> str:
        if activity_percent >= RECOMMENDED_ACTIVITY_THRESHOLD:
            return COLOR_GREEN
        elif activity_percent >= MIN_ACTIVITY_THRESHOLD:
            return COLOR_YELLOW
        return COLOR_RED

    def _apply_body_color(self, color: str):
        self.body_frame.configure(bg=color)
        for widgets in self.metric_labels.values():
            widgets["frame"].configure(bg=color)
            widgets["label"].configure(bg=color)
            widgets["value"].configure(bg=color)

    def _update_metrics(self):
        try:
            stats = self.stats_provider()
        except Exception:
            return

        if "active_time" in self.metric_labels:
            self.metric_labels["active_time"]["value"].configure(
                text=format_duration(stats["active_seconds"])
            )
        if "session_count" in self.metric_labels:
            self.metric_labels["session_count"]["value"].configure(
                text=str(stats["session_count"])
            )
        if "activity_percent" in self.metric_labels:
            self.metric_labels["activity_percent"]["value"].configure(
                text=f"{stats['activity_percent']:.1f}%"
            )

        self._apply_body_color(self._get_body_color(stats["activity_percent"]))

    def _schedule_update(self):
        self._update_metrics()
        self.root.after(WIDGET_UPDATE_INTERVAL * 1000, self._schedule_update)

    # --- Перетаскивание ---

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self.window.winfo_x() + event.x - self._drag_x
        y = self.window.winfo_y() + event.y - self._drag_y
        self.window.geometry(f"+{x}+{y}")

    # --- Управление ---

    def _toggle_minimize(self):
        """Сворачивает/разворачивает тело виджета"""
        if self._minimized:
            self.body_frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.body_frame.pack_forget()

        self._minimized = not self._minimized
        self.window.update_idletasks()
        width = 250
        win_h = self.window.winfo_reqheight()
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.geometry(f"{width}x{win_h}+{x}+{y}")

    def close(self):
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
