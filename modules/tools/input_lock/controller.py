"""
Инструмент «Блокировка ввода»: жизненный цикл блокировки.

Здесь собирается всё, что нельзя делать в hook-потоке: плашка, таймер
автоснятия, реакция на блокировку сессии, диалоги об ошибках. Из фильтра
(blocker.py) сюда приходит единственный сигнал — «нажата комбинация», и он
переадресуется в поток Tk.

Про учёт времени блокировка не знает почти ничего, и это осознанно: время
идёт ровно так же, как если бы пользователь просто ничего не нажимал. Отсчёт
до простоя не замирает, и если продержать блокировку дольше таймаута, день
честно уйдёт в простой. Отличие ровно одно: проглоченные нажатия отсчёт не
сбрасывают — до учёта они не доходят.

Исключение — сама комбинация: её нажатие вводом является (человек за
клавиатурой), поэтому переключение блокировки отмечается через
`events_monitor.note_input`. Разблокировал — значит вернулся к работе, и
отсчёт стартует с этого момента.

Границы возможного: LL-хуки не перехватывают Ctrl+Alt+Del и Win+L — это
защищено самой Windows и обходится только драйвером. Блокировка здесь
мягкая: аварийный выход у пользователя есть всегда, и это скорее плюс.
"""

import time
import tkinter as tk
from tkinter import messagebox

import config
from texts import (
    INPUT_LOCK_HOTKEY_INVALID_TEXT,
    INPUT_LOCK_HOTKEY_INVALID_TITLE,
    INPUT_LOCK_UNAVAILABLE_TEXT,
    INPUT_LOCK_UNAVAILABLE_TITLE,
    TOOL_INPUT_LOCK_LABEL,
    TOOL_INPUT_LOCK_TITLE,
)
from modules import events_monitor
from modules.tools.spec import SETTING_BOOL, SETTING_INT, SETTING_TEXT

from . import blocker
from .hotkey import parse_hotkey
from .overlay import LockOverlay

# Как часто обновляется плашка и проверяется срок автоснятия.
_TICK_MS = 1000


def _validate_hotkey(value: str):
    """Не даёт сохранить комбинацию, которую потом нечем будет распознать."""
    if parse_hotkey(value) is None:
        return (
            INPUT_LOCK_HOTKEY_INVALID_TITLE,
            INPUT_LOCK_HOTKEY_INVALID_TEXT.format(hotkey=value),
        )
    return None


class InputLockTool:
    """Блокирует клавиатуру и мышь до нажатия заданной комбинации."""

    key = "input_lock"
    title = TOOL_INPUT_LOCK_TITLE
    label = TOOL_INPUT_LOCK_LABEL

    # Схема настроек для вкладки «Инструменты» (формат — в modules/tools/registry.py).
    SETTINGS = [
        {
            "key": "INPUT_LOCK_HOTKEY",
            "kind": SETTING_TEXT,
            "label": "Комбинация:",
            "hint": "блокирует и разблокирует",
            "width": 22,
            "validate": _validate_hotkey,
        },
        {
            "key": "INPUT_LOCK_MAX_MINUTES",
            "kind": SETTING_INT,
            "label": "Снять автоматически через (мин):",
            "hint": "0 = не снимать",
            "from": 0,
            "to": 480,
            "step": 5,
        },
        {
            "key": "INPUT_LOCK_RELEASE_ON_SESSION_LOCK",
            "kind": SETTING_BOOL,
            "label": "Снимать при блокировке сессии (Win+L)",
        },
        {
            "key": "INPUT_LOCK_SHOW_OVERLAY",
            "kind": SETTING_BOOL,
            "label": "Показывать плашку «Ввод заблокирован»",
        },
        {
            "key": "INPUT_LOCK_SHOW_HOTKEY_HINT",
            "kind": SETTING_BOOL,
            "label": "Показывать на плашке комбинацию разблокировки",
        },
    ]

    def __init__(self, root: tk.Misc):
        self._root = root
        self._overlay = LockOverlay(root)
        self._deadline: float | None = None
        self._tick_id: str | None = None

    # --- Подключение ---

    def attach(self):
        """Ставит фильтр ввода и подписывается на события сессии."""
        blocker.set_hotkey_callback(self._on_hotkey)
        events_monitor.set_input_filter(blocker.input_filter)
        events_monitor.add_session_listener(self._on_session_change)
        self.refresh()

    def refresh(self):
        """Перечитывает комбинацию из конфига (после диалога настроек)."""
        blocker.set_hotkey(parse_hotkey(config.INPUT_LOCK_HOTKEY))

    def detach(self):
        """Снимает блокировку и фильтр — вызывается при выходе из приложения."""
        self.release("выход из приложения")
        events_monitor.set_input_filter(None)
        blocker.set_hotkey_callback(None)

    # --- Пункты меню «Инструменты» ---

    def menu_items(self) -> list:
        # Пункт всегда только блокирует: пока ввод заблокирован, до меню мышью
        # всё равно не добраться — разблокировка возможна только комбинацией.
        return [(self.label, self.lock)]

    # --- Блокировка ---

    def is_locked(self) -> bool:
        return blocker.is_locked()

    def lock(self):
        if blocker.is_locked():
            return

        error = _validate_hotkey(config.INPUT_LOCK_HOTKEY)
        if error is not None:
            messagebox.showerror(*error, parent=self._root)
            return
        hotkey = parse_hotkey(config.INPUT_LOCK_HOTKEY)

        # Блокировка живёт на хуках монитора ввода: нет их — нечем блокировать.
        if config.INPUT_ACTIVITY_TIMEOUT <= 0:
            messagebox.showwarning(
                INPUT_LOCK_UNAVAILABLE_TITLE,
                INPUT_LOCK_UNAVAILABLE_TEXT,
                parent=self._root,
            )
            return

        blocker.set_hotkey(hotkey)
        blocker.reset_keys()
        blocker.set_locked(True)

        minutes = config.INPUT_LOCK_MAX_MINUTES
        self._deadline = time.monotonic() + minutes * 60 if minutes > 0 else None

        if config.INPUT_LOCK_SHOW_OVERLAY:
            self._overlay.show(
                hotkey.label if config.INPUT_LOCK_SHOW_HOTKEY_HINT else None,
            )
        self._schedule_tick()

        print(f"[LOCK] Ввод заблокирован (разблокировка: {hotkey.label})")

    def release(self, reason: str = ""):
        if not blocker.is_locked():
            return

        blocker.set_locked(False)
        # Зажатые в момент блокировки модификаторы до нас могли не «отпуститься»
        # (например, пользователь ушёл на экран блокировки) — забываем их.
        blocker.reset_keys()

        self._deadline = None
        self._cancel_tick()
        self._overlay.hide()

        print(f"[LOCK] Ввод разблокирован{f' ({reason})' if reason else ''}")

    # --- Внутреннее ---

    def _on_hotkey(self):
        """Пришло из hook-потока — переадресуем в поток Tk."""
        try:
            self._root.after(0, self._toggle)
        except (RuntimeError, tk.TclError):
            # Окно уже разрушено (выход из приложения) — блокировать нечего.
            pass

    def _toggle(self):
        # Комбинацию нажал человек — это ввод, даже если фильтр его проглотил.
        # Автоснятие по таймеру и блокировка сессии сюда не приходят: там
        # пользователь ничего не нажимал, и активностью это не является.
        events_monitor.note_input("клавиатура")

        if blocker.is_locked():
            self.release("комбинация")
        else:
            self.lock()

    def _on_session_change(self, started: bool):
        """Слушатель events_monitor: вызывается в потоке монитора."""
        if started:
            # После экрана блокировки состояние клавиш недостоверно: нажатия
            # на защищённом рабочем столе наши хуки не видят.
            blocker.reset_keys()
            return
        if config.INPUT_LOCK_RELEASE_ON_SESSION_LOCK:
            try:
                self._root.after(0, lambda: self.release("блокировка сессии"))
            except (RuntimeError, tk.TclError):
                pass

    def _schedule_tick(self):
        self._cancel_tick()
        self._tick_id = self._root.after(_TICK_MS, self._tick)

    def _cancel_tick(self):
        if self._tick_id is not None:
            try:
                self._root.after_cancel(self._tick_id)
            except (ValueError, tk.TclError):
                pass
            self._tick_id = None

    def _tick(self):
        self._tick_id = None
        if not blocker.is_locked():
            return

        if self._deadline is None:
            self._overlay.update_remaining(None)
        else:
            remaining = int(self._deadline - time.monotonic())
            if remaining <= 0:
                self.release("истёк таймер автоснятия")
                return
            self._overlay.update_remaining(remaining)

        self._schedule_tick()
