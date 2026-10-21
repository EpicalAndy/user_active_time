"""
Ядро UI-процесса: корень Tk, общий тикер и раздача данных.

Окно-конфигуратор (`ActivityWidget`), мини-виджеты (`WidgetManager`), значок
трея и звуковые сигналы (`SoundAlerts`) — равноправные потребители одних и
тех же данных. Ядро раз в WIDGET_UPDATE_INTERVAL берёт stats и раздаёт всем,
раз в секунду — остаток до неактивности, раз в 500мс — шаг мигания (чтобы
счётчики в заголовке и на мини-виджете мигали в одну фазу). Окно можно
спрятать в трей — остальное от этого не зависит.

Здесь же живут то, что переживает пересборку окна при смене темы, и выход:
инструменты (иначе блокировка ввода снималась бы вместе с окном) и трей.
"""

import tkinter as tk
from collections.abc import Callable

import config
from modules import tools
from modules.events_monitor import get_countdown_remaining
from .alerts import SoundAlerts
from .manager import WidgetManager
from .notification import play_notification, play_tick
from .tray import create_tray
from .widget import ActivityWidget, is_widget_enabled

# Шаг общего тикера: мигание — каждый шаг, секундные события — каждый второй.
_TICK_MS = 500


class App:
    """Владелец корня Tk, тикера и всех потребителей данных."""

    def __init__(self, stats_provider: Callable[[], dict]):
        self._stats_provider = stats_provider
        self._tick_count = 0
        self.root = tk.Tk()
        self.root.withdraw()

        self._manager = WidgetManager(self.root, stats_provider)
        self._tools = tools.create_tools(self.root)
        self._alerts = SoundAlerts(play_goal=play_notification, play_tick=play_tick)
        # Колбэки pystray приходят из его потока — в Tk переадресуем через after.
        # Трей создаётся до окна: окно спрашивает, есть ли куда сворачиваться.
        self._tray = create_tray(
            on_open=lambda: self.root.after(0, self._window.show),
            on_toggle=lambda: self.root.after(0, self._window.toggle_visible),
            on_quit=lambda: self.root.after(0, self.close),
        )
        # Окно без единой строки тела ничего не показывает — тогда оно ждёт
        # в трее, а работают мини-виджеты. Без трея прятать некуда: иначе
        # приложение нельзя было бы ни настроить, ни закрыть.
        self._window = ActivityWidget(
            self.root,
            self._manager,
            tool_items=lambda: tools.menu_items(self._tools),
            tray_available=self._tray is not None,
            start_hidden=self._tray is not None and not is_widget_enabled(),
            on_settings_saved=self._on_settings_saved,
            on_data_changed=self.refresh,
            on_quit=self.close,
        )
        self._manager.restore()
        self._tick()

    # --- Данные ---

    def refresh(self):
        """Берёт свежие stats и раздаёт всем потребителям."""
        try:
            stats = self._stats_provider()
        except Exception:
            return
        self._window.update(stats)
        self._manager.update(stats)
        if self._tray is not None:
            self._tray.update_stats(stats)
        self._alerts.update(stats)

    def _tick(self):
        self._window.tick_blink()
        self._manager.tick_blink()

        if self._tick_count % 2 == 0:
            remaining = get_countdown_remaining()
            self._window.tick_second(remaining)
            self._manager.tick_second()
            self._alerts.tick_second(remaining)

        update_every = config.WIDGET_UPDATE_INTERVAL * 1000 // _TICK_MS
        if self._tick_count % update_every == 0:
            self.refresh()

        # Промежуточное сохранение сессии ведёт фоновый монитор
        # (session_monitor/checkpoint.py) — UI только отображает данные.
        self._tick_count = (self._tick_count + 1) % update_every
        self.root.after(_TICK_MS, self._tick)

    # --- Настройки ---

    def _on_settings_saved(self, theme_changed: bool):
        """Применяет сохранённые настройки ко всем, кого они касаются."""
        # Инструменты читают свои настройки при подключении — после сохранения
        # им нужно перечитать их (например, изменённую комбинацию блокировки).
        tools.refresh_tools(self._tools)
        if theme_changed:
            self._window.apply_theme()
            self._manager.apply_theme()
        else:
            self._window.rebuild_content()
        self.refresh()  # перерисует и содержимое мини-виджетов

    # --- Жизненный цикл ---

    def close(self):
        self._window.save_position()
        tools.detach_tools(self._tools)
        if self._tray is not None:
            self._tray.stop()
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
