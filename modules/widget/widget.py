"""
Виджет отображения активности на рабочем столе
"""

import datetime
import json
import os
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

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
from constants import (
    REPORT_NO_DATA_TITLE,
    REPORT_NO_PAST_TEXT,
    REPORT_NO_TODAY_TEXT,
)
from modules import theme
from modules.events_monitor import get_countdown_remaining
from modules.heatmap_viewer import HeatmapViewer
from modules.manual_activity_dialog import ManualActivityDialog
from modules.period_report import find_latest_past_report_date, get_report_path
from modules.period_report_dialog import PeriodReportDialog
from modules.session_monitor import checkpoint_session
from modules.report_viewer import ReportViewer
from modules.settings_dialog import SettingsDialog
from .body import WidgetBody
from .notification import play_notification, play_tick
from .title_bar import TitleBar
from .toolbar import WidgetToolbar
from utility import format_date_key

# Фон окна (под телом и тулбаром) и тонкая линия-разделитель читаются
# динамически из theme.* — см. _build_chrome / _apply_theme.

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
        self._last_activity_percent: float | None = None  # кеш для countdown-гейта
        self._tick_count = 0
        self._checkpoint_count = 1  # начинаем с 1, чтобы не срабатывать на первом тике
        self.root = tk.Tk()
        self.root.withdraw()

        self.window = tk.Toplevel(self.root)
        self._setup_window()
        self._build_chrome()
        self._position_window()
        self._tick()

    def _build_chrome(self):
        """Создаёт «хромированную» часть виджета: заголовок, тулбар,
        разделитель и тело. Вынесено отдельно, чтобы пересобирать всё это
        при смене темы (уже созданные tk-виджеты сами не перекрашиваются).
        """
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
            on_today_report=self._open_today_report,
            on_last_report=self._open_last_report,
        )
        self._toolbar.pack(fill=tk.X)
        self._toolbar_separator = tk.Frame(self.window, bg=theme.COLOR_MUTED, height=1)
        self._toolbar_separator.pack(fill=tk.X)
        self._body = WidgetBody(self.window)
        self._body.pack(fill=tk.BOTH, expand=True)

    def _setup_window(self):
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        # highlight* — это рамка, которой мы мигаем при предупреждении.
        # По умолчанию красим в WINDOW_BG, чтобы она была невидимой.
        self.window.configure(
            bg=theme.COLOR_DARK_BG,
            highlightthickness=2,
            highlightbackground=theme.COLOR_DARK_BG,
            highlightcolor=theme.COLOR_DARK_BG,
        )

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
            self._last_activity_percent = None
            return

        self._title_bar.update_metric_labels(stats)
        # Кешируем для _update_countdown: он бегает в 60 раз чаще, чем мы
        # обновляем stats, и тянуть stats_provider() каждую секунду накладно.
        self._last_activity_percent = stats["activity_percent"]

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

        goal_reached = (
            self._last_activity_percent is not None
            and self._last_activity_percent >= config.RECOMMENDED_ACTIVITY_THRESHOLD
        )

        if goal_reached:
            # «Награда»: заголовок и рамка всегда зелёные.
            # Чекбокс контролирует только сам countdown: показывать «__:__»
            # или продолжать честно тикать.
            self._title_bar.enter_goal_reached(
                show_placeholder=config.STOP_COUNTDOWN_AT_RECOMMENDED,
            )
            if config.STOP_COUNTDOWN_AT_RECOMMENDED:
                # Заполнитель уже выставлен в enter_goal_reached, и тиканья
                # звуком тоже не нужно — норма выработана, отдыхаем.
                return
        else:
            self._title_bar.exit_goal_reached()

        remaining = get_countdown_remaining()
        self._title_bar.update_countdown(remaining)

        # Тиканье часов в предупредительной фазе (мигает жёлтый/красный).
        warning = config.COUNTDOWN_WARNING_SECONDS
        if (
            config.COUNTDOWN_TICK_SOUND
            and remaining is not None
            and warning > 0
            and 0 < remaining <= warning
        ):
            play_tick()

    def _apply_border_alert(self):
        """Красит рамку окна в красный во время предупреждения/нуля countdown'а.

        Цвет берётся из TitleBar — синхронно с миганием текста заголовка.
        """
        color = self._title_bar.countdown_alert_color() or theme.COLOR_DARK_BG
        self.window.configure(highlightbackground=color, highlightcolor=color)

    def _tick(self):
        """Единый тикер виджета (шаг 500мс)"""
        # 500мс — анимация мигания countdown'а (если активна)
        self._title_bar.tick_blink()
        self._apply_border_alert()

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

    def _open_today_report(self):
        """Быстрое открытие отчёта за сегодня."""
        path = get_report_path(datetime.date.today())
        if not os.path.exists(path):
            messagebox.showinfo(
                REPORT_NO_DATA_TITLE, REPORT_NO_TODAY_TEXT, parent=self.window,
            )
            return
        ReportViewer(self.window, filepath=path)

    def _open_last_report(self):
        """Открывает ближайший по дате прошлый дневной отчёт."""
        date = find_latest_past_report_date(datetime.date.today())
        if date is None:
            messagebox.showinfo(
                REPORT_NO_DATA_TITLE, REPORT_NO_PAST_TEXT, parent=self.window,
            )
            return
        ReportViewer(self.window, filepath=get_report_path(date))

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
        theme_before = theme.current_theme()
        dialog = SettingsDialog(self.window)
        dialog.wait()
        if not dialog.saved:
            return
        if theme.current_theme() != theme_before:
            # Смена темы затрагивает всю «хромированную» часть — пересобираем
            # её целиком (тело тоже, поэтому отдельный _rebuild_body не нужен).
            self._apply_theme()
        else:
            self._rebuild_body()

    def _apply_theme(self):
        """Перекрашивает виджет под текущую тему.

        Окно перекрашиваем напрямую, а заголовок/тулбар/разделитель/тело
        пересобираем: уже созданные tk-виджеты сами цвет не меняют, новые же
        читают палитру динамически из theme.*.
        """
        self.window.configure(
            bg=theme.COLOR_DARK_BG,
            highlightbackground=theme.COLOR_DARK_BG,
            highlightcolor=theme.COLOR_DARK_BG,
        )
        self._title_bar.destroy()
        self._toolbar.destroy()
        self._toolbar_separator.destroy()
        self._body.destroy()
        self._build_chrome()
        if self._minimized:
            self._toolbar.pack_forget()
            self._toolbar_separator.pack_forget()
            self._body.pack_forget()
        self._update_metrics()
        self._resize_window()

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
