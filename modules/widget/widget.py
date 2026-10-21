"""
Виджет отображения активности на рабочем столе — окно-конфигуратор.

Здесь окно и его «хром» (заголовок, тулбар, содержимое), сворачивание (до
заголовка и в трей) и диалоги, которые открываются из тулбара. Данные окно
не добывает само: stats, секундный остаток и шаг мигания ему раздаёт ядро
(`app.App`) — так же, как мини-виджетам и трею. Тело и недельная полоса — в
`content`, действия меню «Отчёты»/«Помощь» — в `actions`, позиция окна между
запусками — в `position`.
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
from modules import theme
from modules.manual_activity_dialog import ManualActivityDialog
from modules.settings import SettingsDialog
from . import actions, position
from .content import WidgetContent
from .countdown_indicator import PROGRESS_NONE, progress_level
from .manager import WidgetManager
from .title_bar import TitleBar
from .toolbar import WidgetToolbar
from .toolbar_reveal import ToolbarReveal
from utility import format_date_key

# Фон окна (под телом и тулбаром) и тонкая линия-разделитель читаются
# динамически из theme.* — см. _build_chrome / apply_theme.

# Ширина виджета — даёт место длинным меткам вроде «До рекомендуемой нормы:»
# плюс склеенным значениям вида «5ч 51м (86.6%)».
WIDGET_WIDTH = 280


def is_widget_enabled() -> bool:
    """Включена ли хотя бы одна строка тела окна (иначе окну нечего показать)."""
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

    def __init__(
        self,
        root: tk.Tk,
        manager: WidgetManager,
        *,
        tool_items: Callable[[], list],
        tray_available: bool,
        start_hidden: bool,
        on_settings_saved: Callable[[bool], None],
        on_data_changed: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._manager = manager  # для диалога 🧩
        self._tool_items = tool_items
        self._tray_available = tray_available
        self._on_settings_saved = on_settings_saved
        self._on_data_changed = on_data_changed
        self._on_quit = on_quit
        self._minimized = False
        self._last_activity_percent: float | None = None  # кеш для countdown-гейта
        # Высота окна зависит от содержимого — после пересборки подгоняем её
        # ещё раз, когда содержимое получит первые stats.
        self._resize_pending = False

        self.window = tk.Toplevel(root)
        if start_hidden:
            # До первой отрисовки: окно не мелькает на экране.
            self.window.withdraw()
        self._setup_window()
        self._build_chrome()
        # Тулбар свёрнутого окна: выезжает при наведении и фокусе. Сам тулбар
        # пересобирается при смене темы, поэтому флаг меню читаем на лету.
        self._toolbar_reveal = ToolbarReveal(
            self.window,
            on_change=self._relayout,
            keep_open=lambda: self._toolbar.menu_open,
        )
        position.place_window(self.window, WIDGET_WIDTH)

    def _build_chrome(self):
        """Создаёт «хромированную» часть виджета: заголовок, тулбар,
        разделитель и тело. Вынесено отдельно, чтобы пересобирать всё это
        при смене темы (уже созданные tk-виджеты сами не перекрашиваются).
        """
        self._title_bar = TitleBar(
            self.window,
            on_close=self._on_quit,
            on_minimize=self._minimize_to_tray,
            on_position_changed=self.save_position,
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
            on_open_changelog=partial(actions.open_changelog, self.window),
            on_open_github=actions.open_github,
            on_open_about=partial(actions.open_about, self.window),
            on_period_report=partial(actions.open_period_report, self.window),
            on_heatmap=partial(actions.open_heatmap, self.window),
            on_today_report=partial(actions.open_today_report, self.window),
            on_last_report=partial(actions.open_last_report, self.window),
            on_open_widgets=self._open_widgets_dialog,
            tool_items=self._tool_items(),
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

    # --- Данные от ядра ---

    def update(self, stats: dict):
        """Свежие stats: тело, полоса, метрики и прогресс в заголовке."""
        # Содержимое обновляется до проверки на нерабочий день: тело в такой
        # день сворачивается в плашку, а недельная полоса остаётся на месте.
        self._content.update(stats)
        if self._resize_pending:
            self._resize_pending = False
            self._resize_window()

        if not stats.get("is_working_day", True):
            self._title_bar.clear_metric_labels()
            self._title_bar.set_progress_level(PROGRESS_NONE)
            self._last_activity_percent = None
            return

        self._title_bar.update_metric_labels(stats)
        self._title_bar.set_progress_level(progress_level(stats["activity_percent"]))
        # Кешируем для tick_second: он бегает в 60 раз чаще, чем приходят stats.
        self._last_activity_percent = stats["activity_percent"]

    def tick_second(self, remaining: int | None):
        """Секундный остаток до неактивности — счётчик в заголовке."""
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
                # Заполнитель уже выставлен в enter_goal_reached.
                return
        else:
            self._title_bar.exit_goal_reached()

        self._title_bar.update_countdown(remaining)

    def tick_blink(self):
        """Шаг мигания (~500мс): счётчик в заголовке, рамка, выезд тулбара."""
        self._title_bar.tick_blink()
        self._apply_border_indicator()
        self._toolbar_reveal.check()

    def _apply_border_indicator(self):
        """Красит рамку окна: прогресс по активности + алерты countdown'а.

        Цвет берётся из TitleBar — синхронно с миганием текста заголовка.
        """
        color = self._title_bar.border_indicator_color() or theme.COLOR_DARK_BG
        self.window.configure(highlightbackground=color, highlightcolor=color)

    # --- Показ и сворачивание ---

    def show(self):
        """Возвращает окно на экран (из трея)."""
        self.window.deiconify()
        self.window.lift()
        position.save_in_tray(False)

    def toggle_visible(self):
        """Двойной клик по значку трея: окно в трее — открыть, на экране — свернуть."""
        if self.window.state() == "withdrawn":
            self.show()
        else:
            self._minimize_to_tray()

    def _minimize_to_tray(self):
        """Прячет окно конфигуратора в трей (мини-виджеты остаются на рабочем столе).

        Значок трея висит всегда, поэтому достаточно скрыть окно. Если трей
        недоступен — откатываемся к сворачиванию до заголовка. Следующий
        запуск начнётся тоже в трее (см. `position.load_in_tray`).
        """
        if self._tray_available:
            self.window.withdraw()
            position.save_in_tray(True)
        else:
            self._toggle_minimize()

    def _toggle_minimize(self):
        """Сворачивает виджет до заголовка и разворачивает обратно.

        Отчёты, настройки и ручное время нужны и без тела, поэтому тулбар
        в свёрнутом виде не пропадает совсем: выезжает, пока курсор над окном
        или фокус в нём (см. ToolbarReveal).
        """
        self._minimized = not self._minimized
        self._toolbar_reveal.set_enabled(self._minimized)
        self._relayout()

    def _apply_layout(self):
        """Раскладывает тулбар, разделитель и тело под заголовком.

        Развёрнутый виджет — все три; свёрнутый — тулбар, только если он
        раскрыт наведением или фокусом. Части перепаковываются заново, чтобы
        их порядок не зависел от того, что и когда пряталось.
        """
        self._toolbar.pack_forget()
        self._toolbar_separator.pack_forget()
        self._content.pack_forget()
        if not self._minimized or self._toolbar_reveal.shown:
            self._toolbar.pack(fill=tk.X)
        if not self._minimized:
            self._toolbar_separator.pack(fill=tk.X)
            self._content.pack()

    def _relayout(self):
        self._apply_layout()
        self._resize_window()

    # --- Диалоги из тулбара ---

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
            self._on_data_changed()

    def _open_settings(self):
        """Открывает диалог настроек; применение — у ядра (`on_settings_saved`)."""
        theme_before = theme.current_theme()
        dialog = SettingsDialog(self.window)
        dialog.wait()
        if dialog.saved:
            self._on_settings_saved(theme.current_theme() != theme_before)

    # --- Пересборка после настроек ---

    def apply_theme(self):
        """Перекрашивает виджет под текущую тему.

        Окно перекрашиваем напрямую, а заголовок/тулбар/разделитель/тело
        пересобираем: уже созданные tk-виджеты сами цвет не меняют, новые же
        читают палитру динамически из theme.*. Содержимое заполнит следующий
        `update(stats)` — ядро зовёт его сразу после этого.
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
        self._relayout()
        self._resize_pending = True

    def rebuild_content(self):
        """Пересоздаёт тело и полосу после изменения настроек"""
        self._title_bar.rebuild_metric_labels()
        self._content.destroy()
        self._content = WidgetContent(self.window)
        self._relayout()
        self._resize_pending = True

    def _resize_window(self):
        """Пересчитывает размер окна под содержимое"""
        self.window.update_idletasks()
        width = WIDGET_WIDTH
        win_h = self.window.winfo_reqheight()
        if self.window.state() == "withdrawn":
            # У спрятанного окна winfo_x/y нулевые — меняем только размер,
            # позиция из place_window сохраняется.
            self.window.geometry(f"{width}x{win_h}")
            return
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.geometry(f"{width}x{win_h}+{x}+{y}")

    def save_position(self):
        """Запоминает позицию окна. Спрятанное в трей окно не трогаем: у
        ни разу не показанного окна координаты нулевые, а позицию показанного
        уже сохранило отпускание после перетаскивания."""
        if self.window.state() != "withdrawn":
            position.save_position(self.window)
