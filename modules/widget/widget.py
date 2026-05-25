"""
Виджет отображения активности на рабочем столе
"""

import datetime
import json
import os
import tkinter as tk
from collections.abc import Callable

from config import (
    LOG_DIR,
    WIDGET_SHOW_ACTIVE_TIME,
    WIDGET_SHOW_ACTIVITY_PERCENT,
    WIDGET_SHOW_FULL_DAY_TIME,
    WIDGET_SHOW_RECOMMENDED_REMAINING,
    WIDGET_SHOW_REMAINING_TIME,
    WIDGET_SHOW_SESSION_COUNT,
)
import config
from constants import COLOR_DARK_BG, COLOR_MUTED
from modules.events_monitor import get_countdown_remaining
from modules.heatmap_viewer import HeatmapViewer
from modules.manual_activity_dialog import ManualActivityDialog
from modules.period_report_dialog import PeriodReportDialog
from modules.session_monitor import checkpoint_session
from modules.report_viewer import ReportViewer
from modules.settings_dialog import SettingsDialog
from .body import WidgetBody
from .notification import play_notification
from .title_bar import TitleBar
from .toolbar import WidgetToolbar
from utility import format_date_key

WINDOW_BG = COLOR_DARK_BG  # фон окна (под телом и тулбаром)
SEPARATOR_COLOR = COLOR_MUTED  # тонкая линия между тулбаром и телом

# Ширина виджета — даёт место длинным меткам вроде «До рекомендуемой нормы:»
# плюс склеенным значениям вида «5ч 51м (86.6%)».
WIDGET_WIDTH = 280

_WIDGET_POS_FILE = os.path.join(LOG_DIR, "widget_position.json")


def is_widget_enabled() -> bool:
    """Проверяет, включена ли хотя бы одна опция отображения"""
    return any([
        WIDGET_SHOW_ACTIVE_TIME,
        WIDGET_SHOW_SESSION_COUNT,
        WIDGET_SHOW_ACTIVITY_PERCENT,
        WIDGET_SHOW_FULL_DAY_TIME,
        WIDGET_SHOW_REMAINING_TIME,
        WIDGET_SHOW_RECOMMENDED_REMAINING,
    ])


class ActivityWidget:
    """Минималистичный виджет активности на рабочем столе"""

    def __init__(self, stats_provider: Callable[[], dict]):
        self.stats_provider = stats_provider
        self._minimized = False
        self._goal_notified = False
        self._tick_count = 0
        self._checkpoint_count = 1  # начинаем с 1, чтобы не срабатывать на первом тике
        self.root = tk.Tk()
        self.root.withdraw()

        self.window = tk.Toplevel(self.root)
        self._setup_window()
        self._title_bar = TitleBar(
            self.window,
            on_close=self.close,
            on_minimize=self._toggle_minimize,
            on_position_changed=self._save_position,
        )
        self._toolbar = WidgetToolbar(
            self.window,
            on_add_active_time=self._add_active_time,
            on_open_reports=lambda: os.startfile(LOG_DIR),
            on_view_report=self._view_report,
            on_open_settings=self._open_settings,
            on_period_report=self._open_period_report,
            on_heatmap=self._open_heatmap,
        )
        self._toolbar.pack(fill=tk.X)
        self._toolbar_separator = tk.Frame(self.window, bg=SEPARATOR_COLOR, height=1)
        self._toolbar_separator.pack(fill=tk.X)
        self._body = WidgetBody(self.window)
        self._body.pack(fill=tk.BOTH, expand=True)
        self._position_window()
        self._tick()

    def _setup_window(self):
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        self.window.configure(bg=WINDOW_BG)

    # --- Позиционирование ---

    def _position_window(self):
        self.window.update_idletasks()
        width = WIDGET_WIDTH
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

    def _update_metrics(self):
        try:
            stats = self.stats_provider()
        except Exception:
            return

        # Тело и заголовок сами решают, как реагировать на нерабочий день.
        self._body.update(stats)

        if not stats.get("is_working_day", True):
            self._title_bar.clear_metric_labels()
            return

        self._title_bar.update_metric_labels(stats)

        # Уведомление о достижении рекомендуемого порога активности
        if config.SOUND_NOTIFICATION and stats["activity_percent"] >= config.RECOMMENDED_ACTIVITY_THRESHOLD:
            if not self._goal_notified:
                self._goal_notified = True
                play_notification()
        else:
            self._goal_notified = False

    def _update_countdown(self):
        if not self._title_bar.has_countdown():
            return
        if not self._body.is_working_day():
            self._title_bar.clear_countdown()
            return
        self._title_bar.update_countdown(get_countdown_remaining())

    def _tick(self):
        """Единый тикер виджета (шаг 500мс)"""
        # 500мс — анимация мигания countdown'а (если активна)
        self._title_bar.tick_blink()

        # 1с — countdown
        if self._tick_count % 2 == 0:
            self._update_countdown()

        # WIDGET_UPDATE_INTERVAL — метрики
        update_every = config.WIDGET_UPDATE_INTERVAL * 2
        if self._tick_count % update_every == 0:
            self._update_metrics()

        # CHECKPOINT_INTERVAL — промежуточное сохранение
        if config.CHECKPOINT_INTERVAL > 0:
            checkpoint_every = config.CHECKPOINT_INTERVAL * 2
            if self._checkpoint_count % checkpoint_every == 0:
                checkpoint_session()
            self._checkpoint_count = (self._checkpoint_count + 1) % checkpoint_every

        self._tick_count = (self._tick_count + 1) % update_every
        self.root.after(500, self._tick)

    # --- Управление ---

    def _toggle_minimize(self):
        """Сворачивает/разворачивает тело виджета"""
        if self._minimized:
            self._toolbar.pack(fill=tk.X)
            self._toolbar_separator.pack(fill=tk.X)
            self._body.pack(fill=tk.BOTH, expand=True)
        else:
            self._toolbar.pack_forget()
            self._toolbar_separator.pack_forget()
            self._body.pack_forget()
        self._minimized = not self._minimized
        self._resize_window()

    def _view_report(self):
        """Открывает визуализацию отчёта"""
        ReportViewer(self.window)

    def _open_period_report(self):
        """Открывает диалог построения отчёта за период"""
        PeriodReportDialog(self.window)

    def _open_heatmap(self):
        """Открывает окно тепловой карты активности"""
        HeatmapViewer(self.window)

    def _add_active_time(self):
        """Открывает диалог управления ручным активным временем"""
        today = format_date_key(datetime.date.today())
        dialog = ManualActivityDialog(self.window, today)
        dialog.wait()
        if dialog.changed:
            self._update_metrics()

    def _open_settings(self):
        """Открывает диалог настроек"""
        dialog = SettingsDialog(self.window)
        dialog.wait()
        if dialog.saved:
            self._rebuild_body()

    def _rebuild_body(self):
        """Пересоздаёт тело виджета после изменения настроек"""
        self._title_bar.rebuild_metric_labels()
        self._body.destroy()
        self._body = WidgetBody(self.window)
        self._body.pack(fill=tk.BOTH, expand=True)
        if self._minimized:
            self._toolbar.pack_forget()
            self._toolbar_separator.pack_forget()
            self._body.pack_forget()
        self._update_metrics()
        self._resize_window()

    def _resize_window(self):
        """Пересчитывает размер окна под содержимое"""
        self.window.update_idletasks()
        width = WIDGET_WIDTH
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
