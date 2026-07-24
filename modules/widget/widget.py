"""
Виджет отображения активности на рабочем столе
"""

import datetime
import json
import os
import tkinter as tk
import webbrowser
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
    GITHUB_URL,
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
from .manager import WidgetManager
from .mini import type_menu_items
from .notification import play_notification, play_tick
from .title_bar import PROGRESS_GOAL, PROGRESS_MIN, PROGRESS_NONE, TitleBar
from .toolbar import WidgetToolbar
from utility import format_date_key, resource_path

# Фон окна (под телом и тулбаром) и тонкая линия-разделитель читаются
# динамически из theme.* — см. _build_chrome / _apply_theme.

# Ширина виджета — даёт место длинным меткам вроде «До рекомендуемой нормы:»
# плюс склеенным значениям вида «5ч 51м (86.6%)».
WIDGET_WIDTH = 280

_WIDGET_POS_FILE = os.path.join(LOG_DIR, "widget_position.json")


def _progress_level(activity_percent: float) -> str:
    """Уровень прогресса по тем же порогам, что и подсветка метрик в теле."""
    if activity_percent >= config.RECOMMENDED_ACTIVITY_THRESHOLD:
        return PROGRESS_GOAL
    if activity_percent >= config.MIN_ACTIVITY_THRESHOLD:
        return PROGRESS_MIN
    return PROGRESS_NONE


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
        self.root = tk.Tk()
        self.root.withdraw()

        # Менеджер мини-виджетов рабочего стола (создаётся до _build_chrome:
        # тулбар берёт из него колбэк добавления).
        self._manager = WidgetManager(self.root, stats_provider)
        self._tray = None  # значок трея (создаётся ниже; None если трей недоступен)

        self.window = tk.Toplevel(self.root)
        self._setup_window()
        self._build_chrome()
        self._position_window()
        self._manager.restore()
        self._tray = self._create_tray()
        self._tick()

    def _build_chrome(self):
        """Создаёт «хромированную» часть виджета: заголовок, тулбар,
        разделитель и тело. Вынесено отдельно, чтобы пересобирать всё это
        при смене темы (уже созданные tk-виджеты сами не перекрашиваются).
        """
        self._title_bar = TitleBar(
            self.window,
            on_close=self.close,
            on_minimize=self._minimize_to_tray,
            on_position_changed=self._save_position,
            on_collapse=self._toggle_minimize,
        )
        self._toolbar = WidgetToolbar(
            self.window,
            on_add_active_time=self._add_active_time,
            on_open_reports=lambda: os.startfile(LOG_DIR),
            on_view_report=self._view_report,
            on_open_settings=self._open_settings,
            on_open_readme=self._open_readme,
            on_open_github=lambda: webbrowser.open(GITHUB_URL),
            on_period_report=self._open_period_report,
            on_heatmap=self._open_heatmap,
            on_today_report=self._open_today_report,
            on_last_report=self._open_last_report,
            on_add_widget=self._manager.add,
            widget_types=type_menu_items(),
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
        # highlight* — это рамка-индикатор (прогресс по активности, алерты
        # countdown'а). По умолчанию красим в WINDOW_BG, чтобы она была невидимой.
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
        # Мини-виджеты рабочего стола — та же частота, тот же stats.
        self._manager.update(stats)

        if not stats.get("is_working_day", True):
            self._title_bar.clear_metric_labels()
            self._title_bar.set_progress_level(PROGRESS_NONE)
            self._last_activity_percent = None
            return

        self._title_bar.update_metric_labels(stats)
        self._title_bar.set_progress_level(_progress_level(stats["activity_percent"]))
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

    def _apply_border_indicator(self):
        """Красит рамку окна: прогресс по активности + алерты countdown'а.

        Цвет берётся из TitleBar — синхронно с миганием текста заголовка.
        """
        color = self._title_bar.border_indicator_color() or theme.COLOR_DARK_BG
        self.window.configure(highlightbackground=color, highlightcolor=color)

    def _tick(self):
        """Единый тикер виджета (шаг 500мс)"""
        # 500мс — анимация мигания countdown'а (если активна)
        self._title_bar.tick_blink()
        self._apply_border_indicator()

        # 1с — countdown
        if self._tick_count % 2 == 0:
            self._update_countdown()

        # WIDGET_UPDATE_INTERVAL — метрики
        update_every = config.WIDGET_UPDATE_INTERVAL * 2
        if self._tick_count % update_every == 0:
            self._update_metrics()

        # Промежуточное сохранение сессии теперь ведёт фоновый монитор
        # (session_monitor._checkpoint_loop) — виджет только отображает данные.

        self._tick_count = (self._tick_count + 1) % update_every
        self.root.after(500, self._tick)

    # --- Управление ---

    def _create_tray(self):
        """Создаёт и запускает значок в трее. None, если трей недоступен.

        Импорт pystray/Pillow ленивый: если зависимостей нет, приложение
        продолжает работать, а кнопка «—» откатывается к сворачиванию до заголовка.
        """
        try:
            from .tray import TrayIcon
        except Exception as e:
            import sys
            print(f"[TRAY] Значок трея отключён — нет зависимости ({e}). "
                  f"Установите: \"{sys.executable}\" -m pip install pystray Pillow")
            return None
        try:
            tray = TrayIcon(
                on_open=lambda: self.root.after(0, self._show_from_tray),
                on_quit=lambda: self.root.after(0, self.close),
            )
            tray.start()
            return tray
        except Exception as e:
            print(f"[TRAY] Не удалось запустить значок трея: {e}")
            return None

    def _minimize_to_tray(self):
        """Прячет окно конфигуратора в трей (мини-виджеты остаются на рабочем столе).

        Значок трея висит всегда, поэтому достаточно скрыть окно. Если трей
        недоступен — откатываемся к сворачиванию до заголовка.
        """
        if self._tray is not None:
            self.window.withdraw()
        else:
            self._toggle_minimize()

    def _show_from_tray(self):
        """Возвращает окно конфигуратора из трея (двойной клик / «Открыть»)."""
        self.window.deiconify()
        self.window.lift()

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
        # Принудительный чекпойнт — чтобы файл отчёта отражал идущую сессию
        # вплоть до текущего момента, а не до последнего автосохранения.
        checkpoint_session()
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

    def _open_readme(self):
        """Открывает локальный README проекта в приложении по умолчанию."""
        path = resource_path("README.md")
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning(
                "Помощь", f"Файл README не найден:\n{path}",
            )

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
        if self._tray is not None:
            self._tray.stop()
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
