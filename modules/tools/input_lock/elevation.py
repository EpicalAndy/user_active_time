"""
Окно с повышенными правами на переднем плане — когда блокировка не действует.

Windows (UIPI) не отдаёт LL-хукам ввод, адресованный окну процесса с более
высоким уровнем целостности: окну, запущенному от администратора, агенту
SYSTEM (уведомления антивируса, установщики). Пока такое окно активно,
фильтр blocker.py просто не вызывается — ввод идёт мимо. Обойти это можно
только правами администратора или подписанным UIAccess-приложением из
Program Files, поэтому здесь ситуация лишь распознаётся, чтобы плашка
сказала о ней честно.

Уровень целостности читается из токена процесса. Токен SYSTEM-процесса
обычному пользователю, как правило, не открыть — отказ доступа тоже считаем
повышенными правами: процесс, в чей токен нам не заглянуть, привилегированнее нас.

Вызывается из потока Tk раз в тик блокировки, не из hook-потока.
"""

import ctypes
import os
from ctypes import wintypes

from winapi import (
    PROCESS_QUERY_LIMITED_INFORMATION,
    SID_AND_ATTRIBUTES,
    TOKEN_INTEGRITY_LEVEL,
    TOKEN_QUERY,
    advapi32,
    kernel32,
    user32,
)

# Уровень целостности нашего процесса: читается при первой проверке.
_own_level: int | None = None


def _integrity_level(process: int) -> int | None:
    """RID метки целостности токена процесса (0x2000 — Medium, 0x3000 — High,
    0x4000 — System). None, если токен не открыть или не прочитать."""
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(size))
        if not size.value:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(
            token, TOKEN_INTEGRITY_LEVEL, buffer, size, ctypes.byref(size),
        ):
            return None
        sid = ctypes.cast(buffer, ctypes.POINTER(SID_AND_ATTRIBUTES)).contents.Sid
        count = advapi32.GetSidSubAuthorityCount(sid).contents.value
        return advapi32.GetSidSubAuthority(sid, count - 1).contents.value
    finally:
        kernel32.CloseHandle(token)


def _image_name(process: int) -> str:
    """Имя exe процесса («AvAgentUI.exe») или "", если узнать не удалось."""
    size = wintypes.DWORD(260)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
        return ""
    return os.path.basename(buffer.value)


def elevated_foreground() -> str | None:
    """Проверяет, привилегированнее ли нас процесс активного окна.

    None — нет (или окна нет, или это мы сами): блокировка действует.
    Строка — да: имя его exe, либо "", если имя не узнать.
    """
    global _own_level
    if _own_level is None:
        _own_level = _integrity_level(kernel32.GetCurrentProcess())
        if _own_level is None:
            return None  # свой токен не прочитан — сравнивать не с чем

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value or pid.value == os.getpid():
        return None

    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        return ""  # не открыть даже на чтение базовых сведений — защищённый процесс
    try:
        level = _integrity_level(process)
        if level is not None and level <= _own_level:
            return None
        return _image_name(process)
    finally:
        kernel32.CloseHandle(process)
