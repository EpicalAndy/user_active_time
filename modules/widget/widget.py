"""
Виджет отображения активности на рабочем столе — окно-конфигуратор.

Здесь то, что держит состояние виджета: окно и его «хром» (заголовок, тулбар,
содержимое), тикер обновления метрик и отсчёта, трей, настройки. Тело и
недельная полоса — в `content`, действия меню «Отчёты»/«Помощь» — в
`actions`, позиция окна между запусками — в `position`.
"""

import datetime
import tkinter as tk
from collections.abc import Callable
from functools import partial

from config import (
    WIDGET_SHOW_ACTIVE_TIME,
    WIDGET_SHOW_ACTIVITY_PERCENT,
    WIDGET_SHOW_FULL_DAY_TIME,
    WIDGET_SHOW_RECOMMENDED_REMAINING,
    WIDGET_SHOW_REMAINING_TIME,
    WIDGET_SHOW_SESSION_COUNT,
)
import config
from modules import theme, tools
from modules.events_monitor import get_countdown_remaining
from modules.manual_activity_dialog import ManualActivityDialog
from modules.settings import SettingsDialog
from . import actions
from .content import WidgetContent
from .manager import WidgetManager
from .notification import play_notification, play_tick
from .position import place_window, save_position
from .countdown_indicator import PROGRESS_GOAL, PROGRESS_MIN, PROGRESS_NONE
from .title_bar import TitleBar
from .toolbar import WidgetToolbar
from utility import format_date_key, truncate_percent

# Фон окна (под телом и тулбаром) и тонкая линия-разделитель читаются
# динамически из theme.* — см. _build_chrome / _apply_theme.

# Ширина виджета — даёт место длинным меткам вроде «До рекомендуемой нормы:»
# плюс склеенным значениям вида «5ч 51м (86.6%)».
WIDGET_WIDTH = 280


def _progress_level(activity_percent: float) -> str:
    """Уровень прогресса по тем же порогам, что и подсветка метрик в теле.

    Сравнение — по усечённому проценту, как и в теле: рамка меняет цвет ровно
    тогда, когда порог берёт показанное в заголовке число.
    """
    shown = truncate_percent(activity_percent)
    if shown >= config.RECOMMENDED_ACTIVITY_THRESHOLD:
        return PROGRESS_GOAL
    if shown >= config.MIN_ACTIVITY_THRESHOLD:
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
        config.WIDGET_SHOW_DAY_TIMELINE,
        # Недельной полосы достаточно, чтобы окно имело смысл: она показывает
        # прошедшие дни, даже когда все дневные метрики выключены.
        config.WIDGET_SHOW_WEEK_ACTIVITY,
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

        # Инструменты (меню 🧰) — тоже до _build_chrome: тулбар берёт у них
        # пункты меню. Живут дольше «хрома»: пересборка при смене темы их
        # не трогает, иначе блокировка ввода снималась бы вместе с окном.
        self._tools = tools.create_tools(self.root)

        self.window = tk.Toplevel(self.root)
        self._setup_window()
        self._build_chrome()
        place_window(self.window, WIDGET_WIDTH)
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
            on_position_changed=lambda: save_position(self.window),
            on_collapse=self._toggle_minimize,
        )
        self._toolbar = WidgetToolbar(
            self.window,
            on_add_active_time=self._add_active_time,
            on_open_reports=actions.open_reports_folder,
            on_view_report=partial(actions.view_report, self.window),
            on_open_settings=self._open_settings,
            on_open_readme=partial(actions.open_user_guide, self.window),
            on_open_dev_guide=partial(actions.open_dev_guide, self.window),
            on_open_github=actions.open_github,
            on_open_about=partial(actions.open_about, self.window),
            on_period_report=partial(actions.open_period_report, self.window),
            on_heatmap=partial(actions.open_heatmap, self.window),
            on_today_report=partial(actions.open_today_report, self.window),
            on_last_report=partial(actions.open_last_report, self.window),
            on_open_widgets=self._open_widgets_dialog,
            tool_items=tools.menu_items(self._tools),
        )
        self._toolbar.pack(fill=tk.X)
        self._toolbar_separator = tk.Frame(self.window, bg=theme.COLOR_MUTED, height=1)
        self._toolbar_separator.pack(fill=tk.X)
        self._content = WidgetContent(self.window)

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

    # --- Обновление данных ---

    def _update_metrics(self):
        try:
            stats = self.stats_provider()
        except Exception:
            return

        # Содержимое обновляется до проверки на нерабочий день: тело в такой
        # день сворачивается в плашку, а недельная полоса остаётся на месте.
        self._content.update(stats)
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
        if not self._content.is_working_day():
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
        # 500мс — анимация мигания countdown'а (если активна): в заголовке
        # и в мини-виджетах, чтобы мигали в одну фазу.
        self._title_bar.tick_blink()
        self._apply_border_indicator()
        self._manager.tick_blink()

        # 1с — countdown (в заголовке и в мини-виджетах, которым мало stats)
        if self._tick_count % 2 == 0:
            self._update_countdown()
            self._manager.tick_second()

        # WIDGET_UPDATE_INTERVAL — метрики
        update_every = config.WIDGET_UPDATE_INTERVAL * 2
        if self._tick_count % update_every == 0:
            self._update_metrics()

        # Промежуточное сохранение сессии теперь ведёт фоновый монитор
        # (session_monitor/checkpoint.py) — виджет только отображает данные.

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
            self._content.pack()
        else:
            self._toolbar.pack_forget()
            self._toolbar_separator.pack_forget()
            self._content.pack_forget()
        self._minimized = not self._minimized
        self._resize_window()

    def _open_widgets_dialog(self):
        """Открывает диалог управления мини-виджетами рабочего стола"""
        from .widgets_dialog import WidgetsDialog
        WidgetsDialog(self.window, self._manager).wait()

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
        # Инструменты читают свои настройки при подключении — после сохранения
        # им нужно перечитать их (например, изменённую комбинацию блокировки).
        tools.refresh_tools(self._tools)
        if theme.current_theme() != theme_before:
            # Смена темы затрагивает всю «хромированную» часть — пересобираем
            # её целиком (тело тоже, поэтому отдельный _rebuild_content не нужен).
            self._apply_theme()
        else:
            self._rebuild_content()

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
        self._content.destroy()
        self._build_chrome()
        if self._minimized:
            self._toolbar.pack_forget()
            self._toolbar_separator.pack_forget()
            self._content.pack_forget()
        self._update_metrics()
        self._resize_window()

    def _rebuild_content(self):
        """Пересоздаёт тело и полосу после изменения настроек"""
        self._title_bar.rebuild_metric_labels()
        self._content.destroy()
        self._content = WidgetContent(self.window)
        if self._minimized:
            self._toolbar.pack_forget()
            self._toolbar_separator.pack_forget()
            self._content.pack_forget()
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

    def close(self):
        save_position(self.window)
        tools.detach_tools(self._tools)
        if self._tray is not None:
            self._tray.stop()
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
