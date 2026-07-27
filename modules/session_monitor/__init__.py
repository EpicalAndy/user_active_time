"""
Монитор логинов/разлогинов пользователя Windows.
Работает без прав администратора.

Пакет собран слоями снизу вверх, импорты идут строго в одну сторону:

    state_store   — state.json и схема записи дня
    journal       — строки лога дня (чистый текст, без I/O)
    activity      — пересчёт активного времени и таймлайна из сырых интервалов
    day_report    — мост day_state ↔ дневной JSON-отчёт
    session       — владелец рантайма (session_start_time, state_lock)
                    и жизненный цикл: start/end/checkpoint/recover, log_event
    checkpoint    — фоновый таймер промежуточного сохранения
    stats         — get_current_stats для виджета
    manual_time   — ручное добавление/удаление активного времени
    win_events    — WTS-подписка, скрытое окно, цикл сообщений, main()

Этот модуль — фасад: внешние потребители импортируют всё отсюда,
    from modules.session_monitor import get_current_stats
и не зависят от внутренней раскладки пакета.
"""

from .manual_time import (
    add_manual_active_time,
    get_manual_active_entries,
    remove_manual_active_time,
)
from .session import checkpoint_session, end_session, log_event, start_session
from .stats import get_current_stats
from .win_events import main, request_stop

__all__ = [
    "add_manual_active_time",
    "checkpoint_session",
    "end_session",
    "get_current_stats",
    "get_manual_active_entries",
    "log_event",
    "main",
    "remove_manual_active_time",
    "request_stop",
    "start_session",
]
