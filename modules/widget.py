"""
Виджет отображения активности на рабочем столе
"""

import datetime
import json
import math
import os
import struct
import tkinter as tk
import wave
import winsound
from collections.abc import Callable

from config import (
    CHECKPOINT_INTERVAL,
    COUNTDOWN_WARNING_SECONDS,
    LOG_DIR,
    INPUT_ACTIVITY_TIMEOUT,
    MIN_ACTIVITY_THRESHOLD,
    RECOMMENDED_ACTIVITY_THRESHOLD,
    SOUND_NOTIFICATION,
    WIDGET_SHOW_ACTIVE_TIME,
    WIDGET_SHOW_ACTIVITY_PERCENT,
    WIDGET_SHOW_FULL_DAY_TIME,
    WIDGET_SHOW_REMAINING_TIME,
    WIDGET_SHOW_SESSION_COUNT,
    WIDGET_SHOW_TITLE_PERCENT,
    WIDGET_SHOW_TITLE_REMAINING_TIME,
    WIDGET_UPDATE_INTERVAL,
    MAIN_FONT_SIZE,
)
import config
from constants import (
    COLOR_DARK_BG,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_HOVER,
    COLOR_LIGHT_FG,
    COLOR_RED,
    COLOR_WHITE,
    COLOR_YELLOW,
    FONT_FAMILY,
    METRIC_ACTIVE_TIME,
    METRIC_ACTIVITY_PERCENT,
    METRIC_FULL_DAY_TIME,
    METRIC_REMAINING_TIME,
    METRIC_SESSION_COUNT,
)
from modules.events_monitor import get_countdown_remaining
from modules.manual_activity_dialog import ManualActivityDialog
from modules.session_monitor import add_manual_active_time, checkpoint_session
from modules.report_viewer import ReportViewer
from modules.settings_dialog import SettingsDialog
from modules.toolbar import WidgetToolbar
from utility import format_date_key, format_duration_short

# Псевдонимы цветов для семантики виджета
TITLE_BG = COLOR_DARK_BG
TITLE_FG = COLOR_LIGHT_FG
CLOSE_HOVER = COLOR_RED
MINIMIZE_HOVER = COLOR_HOVER
METRIC_FG = COLOR_WHITE

_WIDGET_POS_FILE = os.path.join(LOG_DIR, "widget_position.json")


def _generate_notification_wav() -> str:
    """Генерирует приятный звук уведомления (~2.5с) — восходящий аккорд"""
    sample_rate = 22050
    duration = 2.5
    n_samples = int(sample_rate * duration)

    notes = [
        (523.25, 0.0, 0.9),    # C5
        (659.25, 0.3, 1.2),    # E5
        (783.99, 0.6, 1.5),    # G5
        (1046.50, 1.0, 2.5),   # C6 (fade out)
    ]

    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        value = 0.0
        for freq, start, end in notes:
            if start <= t <= end:
                local_t = (t - start) / (end - start)
                envelope = math.sin(math.pi * local_t)
                value += math.sin(2 * math.pi * freq * t) * envelope * 0.2
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))

    wav_path = os.path.join(LOG_DIR, "notification.wav")
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *samples))
    return wav_path


_NOTIFICATION_WAV_PATH = _generate_notification_wav()


def is_widget_enabled() -> bool:
    """Проверяет, включена ли хотя бы одна опция отображения"""
    return any([
        WIDGET_SHOW_ACTIVE_TIME,
        WIDGET_SHOW_SESSION_COUNT,
        WIDGET_SHOW_ACTIVITY_PERCENT,
        WIDGET_SHOW_FULL_DAY_TIME,
        WIDGET_SHOW_REMAINING_TIME,
    ])


class ActivityWidget:
    """Минималистичный виджет активности на рабочем столе"""

    def __init__(self, stats_provider: Callable[[], dict]):
        self.stats_provider = stats_provider
        self._minimized = False
        self._countdown_blink_bold = False
        self._countdown_blinking = False
        self._is_working_day = True
        self._goal_notified = False
        self._tick_count = 0
        self._checkpoint_count = 1  # начинаем с 1, чтобы не срабатывать на первом тике
        self.root = tk.Tk()
        self.root.withdraw()

        self.window = tk.Toplevel(self.root)
        self._setup_window()
        self._create_title_bar()
        self._toolbar = WidgetToolbar(
            self.window,
            on_add_active_time=self._add_active_time,
            on_open_reports=lambda: os.startfile(LOG_DIR),
            on_view_report=self._view_report,
            on_open_settings=self._open_settings,
        )
        self._toolbar.pack(fill=tk.X)
        self._create_body()
        self._position_window()
        self._tick()

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

        self._title_label = tk.Label(
            title_frame, text="Активность",
            bg=TITLE_BG, fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), padx=MAIN_FONT_SIZE,
        )
        self._title_label.pack(side=tk.LEFT, fill=tk.Y)

        close_btn = tk.Label(
            title_frame, text="  \u2715  ",
            bg=TITLE_BG, fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, fill=tk.Y)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=MINIMIZE_HOVER))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=TITLE_FG))

        self._minimize_btn = tk.Label(
            title_frame, text="  \u2014  ",
            bg=TITLE_BG, fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
        )
        self._minimize_btn.pack(side=tk.RIGHT, fill=tk.Y)
        self._minimize_btn.bind("<Button-1>", lambda e: self._toggle_minimize())
        self._minimize_btn.bind("<Enter>", lambda e: self._minimize_btn.configure(fg=MINIMIZE_HOVER))
        self._minimize_btn.bind("<Leave>", lambda e: self._minimize_btn.configure(fg=TITLE_FG))

        # Счётчик обратного отсчёта до неактивности
        self._countdown_label = None
        if INPUT_ACTIVITY_TIMEOUT > 0:
            self._countdown_label = tk.Label(
                title_frame, text="",
                bg=TITLE_BG, fg=TITLE_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            self._countdown_label.pack(side=tk.LEFT, fill=tk.Y)

        # Процент активности в заголовке
        self._title_percent_label = None
        if WIDGET_SHOW_TITLE_PERCENT:
            self._title_percent_label = tk.Label(
                title_frame, text="",
                bg=TITLE_BG, fg=TITLE_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            self._title_percent_label.pack(side=tk.LEFT, fill=tk.Y)

        # Оставшееся время до конца рабочего дня в заголовке
        self._title_remaining_label = None
        if WIDGET_SHOW_TITLE_REMAINING_TIME:
            self._title_remaining_label = tk.Label(
                title_frame, text="",
                bg=TITLE_BG, fg=TITLE_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            self._title_remaining_label.pack(side=tk.LEFT, fill=tk.Y)

        # Перетаскивание за заголовок
        drag_widgets: list[tk.Widget] = [title_frame, self._title_label]
        if self._countdown_label:
            drag_widgets.append(self._countdown_label)
        if self._title_percent_label:
            drag_widgets.append(self._title_percent_label)
        if self._title_remaining_label:
            drag_widgets.append(self._title_remaining_label)
        for w in drag_widgets:
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", lambda e: self._save_position())

    # --- Тело ---

    def _create_body(self):
        self.body_frame = tk.Frame(self.window, bg=COLOR_RED, padx=12, pady=8)
        self.body_frame.pack(fill=tk.BOTH, expand=True)

        # Сообщение для нерабочего дня (скрыто по умолчанию)
        self._day_off_label = tk.Label(
            self.body_frame, text="Сегодня не рабочий день",
            bg=COLOR_GRAY, fg=METRIC_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
        )

        self.metric_labels = {}

        if WIDGET_SHOW_ACTIVE_TIME:
            self.metric_labels["active_time"] = self._add_metric(f"{METRIC_ACTIVE_TIME}:")
        if WIDGET_SHOW_SESSION_COUNT:
            self.metric_labels["session_count"] = self._add_metric(f"{METRIC_SESSION_COUNT}:")
        if WIDGET_SHOW_ACTIVITY_PERCENT:
            self.metric_labels["activity_percent"] = self._add_metric(f"{METRIC_ACTIVITY_PERCENT}:")
        if WIDGET_SHOW_FULL_DAY_TIME:
            self.metric_labels["full_day_time"] = self._add_metric(f"{METRIC_FULL_DAY_TIME}:")
        if WIDGET_SHOW_REMAINING_TIME:
            self.metric_labels["remaining_time"] = self._add_metric(f"{METRIC_REMAINING_TIME}:")

    def _add_metric(self, label_text: str) -> dict:
        frame = tk.Frame(self.body_frame, bg=COLOR_RED)
        frame.pack(fill=tk.X, pady=2)

        label = tk.Label(
            frame, text=label_text,
            bg=COLOR_RED, fg=METRIC_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W,
        )
        label.pack(side=tk.LEFT)

        value = tk.Label(
            frame, text="\u2014",
            bg=COLOR_RED, fg=METRIC_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"), anchor=tk.E,
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

        saved = self._load_position()
        if saved:
            sx, sy = saved
            if 0 <= sx <= screen_w - width and 0 <= sy <= screen_h - win_h:
                self.window.geometry(f"{width}x{win_h}+{sx}+{sy}")
                return

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

    def _show_day_off(self):
        """Переключает виджет в режим нерабочего дня"""
        self._is_working_day = False
        for widgets in self.metric_labels.values():
            widgets["frame"].pack_forget()
        self._day_off_label.pack(fill=tk.X, pady=8)
        self._apply_body_color(COLOR_GRAY)
        if self._title_percent_label is not None:
            self._title_percent_label.configure(text="")
        if self._title_remaining_label is not None:
            self._title_remaining_label.configure(text="")

    def _show_working_day(self):
        """Переключает виджет в режим рабочего дня"""
        self._is_working_day = True
        self._day_off_label.pack_forget()
        for widgets in self.metric_labels.values():
            widgets["frame"].pack(fill=tk.X, pady=2)

    def _update_metrics(self):
        try:
            stats = self.stats_provider()
        except Exception:
            return

        if not stats.get("is_working_day", True):
            self._show_day_off()
            return

        # Убедиться, что метрики видны (переход с нерабочего дня или после пересоздания)
        if not self._is_working_day:
            self._show_working_day()

        if "active_time" in self.metric_labels:
            self.metric_labels["active_time"]["value"].configure(
                text=format_duration_short(stats["active_seconds"])
            )
        if "session_count" in self.metric_labels:
            self.metric_labels["session_count"]["value"].configure(
                text=str(stats["session_count"])
            )
        if "activity_percent" in self.metric_labels:
            self.metric_labels["activity_percent"]["value"].configure(
                text=f"{stats['activity_percent']:.1f}%"
            )
        if "full_day_time" in self.metric_labels:
            self.metric_labels["full_day_time"]["value"].configure(
                text=format_duration_short(stats["full_day_seconds"])
            )
        if "remaining_time" in self.metric_labels:
            self.metric_labels["remaining_time"]["value"].configure(
                text=format_duration_short(max(0, stats.get("remaining_work_seconds", 0)))
            )

        self._apply_body_color(self._get_body_color(stats["activity_percent"]))

        # Процент активности в заголовке
        if self._title_percent_label is not None:
            self._title_percent_label.configure(
                text=f" {stats['activity_percent']:.1f}%"
            )

        # Оставшееся время до конца рабочего дня в заголовке
        if self._title_remaining_label is not None:
            remaining = max(0, stats.get("remaining_work_seconds", 0))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            self._title_remaining_label.configure(text=f" {hours}ч {minutes}м")

        # Уведомление о достижении рекомендуемого порога активности
        if SOUND_NOTIFICATION and stats["activity_percent"] >= RECOMMENDED_ACTIVITY_THRESHOLD:
            if not self._goal_notified:
                self._goal_notified = True
                winsound.PlaySound(
                    _NOTIFICATION_WAV_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC
                )
        else:
            self._goal_notified = False

    def _update_countdown(self):
        if self._countdown_label is None:
            return
        if not self._is_working_day:
            self._countdown_label.configure(text="")
            self._countdown_blinking = False
            return
        remaining = get_countdown_remaining()
        if remaining is None:
            self._countdown_label.configure(text="")
            self._countdown_blink_bold = False
            return

        minutes, secs = divmod(remaining, 60)
        text = f"{minutes:02d}:{secs:02d}"

        if remaining == 0:
            # Неактивен — жирный красный, мигание выключено
            self._countdown_blinking = False
            self._countdown_blink_bold = False
            self._countdown_label.configure(
                text=text, fg=COLOR_RED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
            )
            self._title_label.configure(
                fg=COLOR_RED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
            )
        elif COUNTDOWN_WARNING_SECONDS > 0 and remaining <= COUNTDOWN_WARNING_SECONDS:
            # Приближение к неактивности — мигание управляется тикером
            self._countdown_label.configure(text=text, fg=TITLE_FG)
            self._countdown_blinking = True
        else:
            # Обычное состояние
            self._countdown_blinking = False
            self._countdown_blink_bold = False
            self._countdown_label.configure(
                text=text, fg=TITLE_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            self._title_label.configure(
                fg=TITLE_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE),
            )

    def _tick(self):
        """Единый тикер виджета (шаг 500мс)"""
        # 500мс — мигание
        if self._countdown_blinking and self._countdown_label is not None:
            self._countdown_blink_bold = not self._countdown_blink_bold
            weight = "bold" if self._countdown_blink_bold else "normal"
            fg = COLOR_RED if self._countdown_blink_bold else TITLE_FG
            self._countdown_label.configure(
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, weight), fg=fg,
            )
            self._title_label.configure(
                font=(FONT_FAMILY, MAIN_FONT_SIZE, weight), fg=fg,
            )

        # 1с — countdown
        if self._tick_count % 2 == 0:
            self._update_countdown()

        # WIDGET_UPDATE_INTERVAL — метрики
        update_every = WIDGET_UPDATE_INTERVAL * 2
        if self._tick_count % update_every == 0:
            self._update_metrics()

        # CHECKPOINT_INTERVAL — промежуточное сохранение
        if CHECKPOINT_INTERVAL > 0:
            checkpoint_every = CHECKPOINT_INTERVAL * 2
            if self._checkpoint_count % checkpoint_every == 0:
                checkpoint_session()
            self._checkpoint_count = (self._checkpoint_count + 1) % checkpoint_every

        self._tick_count = (self._tick_count + 1) % update_every
        self.root.after(500, self._tick)

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
            self._toolbar.pack(fill=tk.X)
            self.body_frame.pack(fill=tk.BOTH, expand=True)
        else:
            self._toolbar.pack_forget()
            self.body_frame.pack_forget()
        self._minimized = not self._minimized
        self._resize_window()

    def _view_report(self):
        """Открывает визуализацию отчёта"""
        ReportViewer(self.window)

    def _add_active_time(self):
        """Открывает диалог ручного добавления активного времени"""
        dialog = ManualActivityDialog(self.window)
        dialog.wait()
        if dialog.result is None:
            return
        start, end, desc = dialog.result
        today = format_date_key(datetime.date.today())
        add_manual_active_time(today, start, end, desc)
        self._update_metrics()

    def _open_settings(self):
        """Открывает диалог настроек"""
        dialog = SettingsDialog(self.window)
        dialog.wait()
        if dialog.saved:
            self._rebuild_body()

    def _rebuild_body(self):
        """Пересоздаёт тело виджета после изменения настроек"""
        self._reload_config()
        self._rebuild_title_labels()
        self.body_frame.destroy()
        self._create_body()
        if self._minimized:
            self._toolbar.pack_forget()
            self.body_frame.pack_forget()
        self._update_metrics()
        self._resize_window()

    def _rebuild_title_labels(self):
        """Пересоздаёт или удаляет лейблы в заголовке по настройкам"""
        self._rebuild_title_label("_title_percent_label", WIDGET_SHOW_TITLE_PERCENT)
        self._rebuild_title_label("_title_remaining_label", WIDGET_SHOW_TITLE_REMAINING_TIME)

    def _rebuild_title_label(self, attr: str, show: bool):
        """Пересоздаёт или удаляет один лейбл заголовка по настройке"""
        label = getattr(self, attr)
        if show and label is None:
            label = tk.Label(
                self._title_frame, text="",
                bg=TITLE_BG, fg=TITLE_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            label.pack(side=tk.LEFT, fill=tk.Y)
            label.bind("<ButtonPress-1>", self._start_drag)
            label.bind("<B1-Motion>", self._on_drag)
            label.bind("<ButtonRelease-1>", lambda e: self._save_position())
            setattr(self, attr, label)
        elif not show and label is not None:
            label.destroy()
            setattr(self, attr, None)

    def _reload_config(self):
        """Перечитывает значения из модуля config"""
        # Импорты на уровне модуля кэшируют значения — обновляем из config напрямую
        global WIDGET_SHOW_ACTIVE_TIME, WIDGET_SHOW_SESSION_COUNT
        global WIDGET_SHOW_ACTIVITY_PERCENT, WIDGET_SHOW_FULL_DAY_TIME
        global WIDGET_SHOW_REMAINING_TIME
        global WIDGET_SHOW_TITLE_PERCENT, WIDGET_SHOW_TITLE_REMAINING_TIME
        global INPUT_ACTIVITY_TIMEOUT, COUNTDOWN_WARNING_SECONDS, CHECKPOINT_INTERVAL
        global SOUND_NOTIFICATION
        WIDGET_SHOW_ACTIVE_TIME = config.WIDGET_SHOW_ACTIVE_TIME
        WIDGET_SHOW_SESSION_COUNT = config.WIDGET_SHOW_SESSION_COUNT
        WIDGET_SHOW_ACTIVITY_PERCENT = config.WIDGET_SHOW_ACTIVITY_PERCENT
        WIDGET_SHOW_FULL_DAY_TIME = config.WIDGET_SHOW_FULL_DAY_TIME
        WIDGET_SHOW_REMAINING_TIME = config.WIDGET_SHOW_REMAINING_TIME
        WIDGET_SHOW_TITLE_PERCENT = config.WIDGET_SHOW_TITLE_PERCENT
        WIDGET_SHOW_TITLE_REMAINING_TIME = config.WIDGET_SHOW_TITLE_REMAINING_TIME
        INPUT_ACTIVITY_TIMEOUT = config.INPUT_ACTIVITY_TIMEOUT
        COUNTDOWN_WARNING_SECONDS = config.COUNTDOWN_WARNING_SECONDS
        CHECKPOINT_INTERVAL = config.CHECKPOINT_INTERVAL
        SOUND_NOTIFICATION = config.SOUND_NOTIFICATION

    def _resize_window(self):
        """Пересчитывает размер окна под содержимое"""
        self.window.update_idletasks()
        width = 250
        win_h = self.window.winfo_reqheight()
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.geometry(f"{width}x{win_h}+{x}+{y}")

    def _load_position(self) -> tuple[int, int] | None:
        """Загружает сохранённую позицию виджета"""
        try:
            with open(_WIDGET_POS_FILE, "r") as f:
                pos = json.load(f)
            return pos["x"], pos["y"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError, IOError):
            return None

    def _save_position(self):
        """Сохраняет текущую позицию виджета"""
        try:
            x = self.window.winfo_x()
            y = self.window.winfo_y()
            with open(_WIDGET_POS_FILE, "w") as f:
                json.dump({"x": x, "y": y}, f)
        except IOError:
            pass

    def close(self):
        self._save_position()
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
