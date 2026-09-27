"""
Чтение и атомарная запись JSON-файлов приложения.

Общие правила для всех хранилищ (state.json, дневные отчёты, календарь,
виджеты, позиция окна): отсутствующий или битый файл — не ошибка, а «данных
нет»; запись идёт через временный файл рядом и `os.replace`, чтобы сбой
посреди записи не оставил на диске полфайла.
"""

import json
import os

from constants import ENCODING


def read_json(path: str):
    """Содержимое JSON-файла или None, если файла нет, он не читается или битый.

    Тип содержимого не проверяется — это дело вызывающего.
    """
    try:
        with open(path, "r", encoding=ENCODING) as f:
            return json.load(f)
    except (OSError, ValueError):  # ValueError: битый JSON и не-UTF-8
        return None


def write_json_atomic(path: str, data) -> None:
    """Записывает data в JSON атомарно: временный файл рядом + os.replace."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding=ENCODING) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
