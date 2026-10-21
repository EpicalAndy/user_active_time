"""
Автозапуск при входе в Windows: запись в HKCU\\...\\CurrentVersion\\Run.

Ветка HKCU принадлежит текущему пользователю — писать туда можно без прав
администратора, в отличие от HKLM или служб. Ярлык в shell:startup тоже не
требует прав, но его создание идёт через COM; запись в реестр проще и видна
в Диспетчере задач на вкладке «Автозагрузка».

Источник истины — сам реестр, а не config.py: запись можно удалить или
выключить в Диспетчере задач, и настройки должны это видеть. Выключение там
не трогает Run, а пишет флаг в соседний ключ StartupApproved\\Run — поэтому
включённой считается только запись, не выключенная этим флагом.

Команда запуска — без консоли: в обычном запуске это pythonw.exe из того же
окружения (venv), что и текущий интерпретатор, плюс main.py; в сборке
PyInstaller — сам исполняемый файл.
"""

import os
import re
import sys
import winreg

from constants import APP_NAME

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
VALUE_NAME = APP_NAME

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch_command() -> str:
    """Команда, которой Windows запустит приложение при входе."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(exe_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{os.path.join(_PROJECT_DIR, "main.py")}"'


def command_paths(command: str) -> list[str]:
    """Пути в кавычках из команды запуска (интерпретатор, скрипт)."""
    return re.findall(r'"([^"]+)"', command)


def is_disabled_flag(data: bytes | None) -> bool:
    """Выключена ли запись флагом StartupApproved (Диспетчер задач).

    Значение — 12 байт: первый байт 0x02/0x06 значит «включено», нечётный
    (0x03, 0x01) — «выключено»; остальное — время выключения.
    """
    return bool(data) and data[0] & 1 == 1


def _read_value(key_path: str) -> object | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return value
    except FileNotFoundError:
        return None


def _delete_value(key_path: str):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass


def registered_command() -> str | None:
    """Команда из Run или None, если записи нет."""
    value = _read_value(_RUN_KEY)
    return value if isinstance(value, str) else None


def is_enabled() -> bool:
    """Есть ли запись в Run, не выключенная в Диспетчере задач."""
    if registered_command() is None:
        return False
    approved = _read_value(_APPROVED_KEY)
    return not is_disabled_flag(approved if isinstance(approved, bytes) else None)


def set_enabled(enabled: bool):
    """Добавляет приложение в автозагрузку или убирает его оттуда.

    Флаг StartupApproved снимается в обоих случаях: при включении он иначе
    оставил бы запись выключенной, при выключении — висел бы мусором.
    Ошибки доступа (например, запрет групповой политикой) — OSError наружу.
    """
    if enabled:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
    else:
        _delete_value(_RUN_KEY)
    _delete_value(_APPROVED_KEY)


def apply(enabled: bool):
    """Приводит автозагрузку к значению галочки из настроек.

    Реестр трогается, только когда состояние меняется или включённая запись
    указывает на несуществующие файлы (папку с программой перенесли).
    Рабочая запись другой копии (например, рабочего дерева разработчика)
    не перезаписывается от простого «OK» в настройках.
    """
    if enabled != is_enabled():
        set_enabled(enabled)
        return
    if enabled:
        command = registered_command() or ""
        if not all(os.path.exists(p) for p in command_paths(command)):
            set_enabled(True)
