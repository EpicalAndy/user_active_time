"""
Фоновый таймер промежуточного сохранения сессии.

Живёт в мониторе, а не в виджете: данные сохраняются независимо от UI — даже
если виджет закрыт или их запущено несколько (иначе чекпойнты либо исчезали бы,
либо дублировались).
"""

import threading
import time

import config
from .session import checkpoint_session

_checkpoint_thread: threading.Thread | None = None
_checkpoint_stop = threading.Event()


def _checkpoint_loop():
    """Цикл промежуточного сохранения.

    Интервал (config.CHECKPOINT_INTERVAL) читается динамически, чтобы менялся
    без перезапуска; 0 отключает промежуточные сохранения (сессия всё равно
    пишется на start/end/событиях).
    """
    last = time.monotonic()
    while not _checkpoint_stop.wait(timeout=1.0):
        interval = config.CHECKPOINT_INTERVAL
        if interval <= 0:
            # Сбрасываем отсчёт, чтобы после включения ждать полный интервал.
            last = time.monotonic()
            continue
        now = time.monotonic()
        if now - last >= interval:
            last = now
            checkpoint_session()


def start_checkpoint_timer():
    """Запускает фоновый поток промежуточного сохранения."""
    global _checkpoint_thread
    _checkpoint_stop.clear()
    _checkpoint_thread = threading.Thread(
        target=_checkpoint_loop, daemon=True, name="CheckpointTimer",
    )
    _checkpoint_thread.start()


def stop_checkpoint_timer():
    """Останавливает фоновый поток промежуточного сохранения."""
    global _checkpoint_thread
    _checkpoint_stop.set()
    if _checkpoint_thread and _checkpoint_thread.is_alive():
        _checkpoint_thread.join(timeout=3)
    _checkpoint_thread = None
