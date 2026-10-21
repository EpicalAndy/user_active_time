"""
Звуковые сигналы: достижение нормы активности и тиканье перед простоем.

Сигналы решаются по данным — stats и остатку до неактивности, — а не по
тому, что сейчас нарисовано: окно-конфигуратор о звуках не знает, и они
одинаково работают, показано оно или спрятано в трей. Ядро приложения
(`App`) кормит сюда те же stats, что и виджетам, и тот же секундный остаток.

Проигрыватели передаются снаружи: `notification` при импорте генерирует
WAV-файлы, а логика сигналов от этого не зависит и проверяется в тестах
без звука.
"""

from collections.abc import Callable

import config


class SoundAlerts:
    """Решает, когда звучит сигнал нормы и когда тикают часы."""

    def __init__(self, play_goal: Callable[[], None], play_tick: Callable[[], None]):
        self._play_goal = play_goal
        self._play_tick = play_tick
        self._goal_notified = False
        # Контекст дня из последних stats: они приходят раз в
        # WIDGET_UPDATE_INTERVAL, а тиканье решается каждую секунду.
        self._is_working_day = True
        self._goal_reached = False

    def update(self, stats: dict):
        """Свежие stats: сигнал нормы (один раз на пересечение порога)."""
        self._is_working_day = stats.get("is_working_day", True)
        if not self._is_working_day:
            # В нерабочий день нормы нет — и состояние сигнала не трогаем.
            self._goal_reached = False
            return
        percent = stats.get("activity_percent", 0)
        self._goal_reached = percent >= config.RECOMMENDED_ACTIVITY_THRESHOLD

        if config.SOUND_NOTIFICATION and self._goal_reached:
            if not self._goal_notified:
                self._goal_notified = True
                self._play_goal()
        else:
            self._goal_notified = False

    def tick_second(self, remaining: int | None):
        """Секундный остаток до неактивности: тиканье в предупредительной фазе.

        Норма выработана и отсчёт остановлен настройкой — не тикаем: отдыхаем.
        """
        if not config.COUNTDOWN_TICK_SOUND or not self._is_working_day:
            return
        if self._goal_reached and config.STOP_COUNTDOWN_AT_RECOMMENDED:
            return
        warning = config.COUNTDOWN_WARNING_SECONDS
        if remaining is not None and warning > 0 and 0 < remaining <= warning:
            self._play_tick()
