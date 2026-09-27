"""
Персист реестра мини-виджетов рабочего стола.

Реестр — плоский список записей вида
    {"id": str, "type": str, "x": int, "y": int, "opts": dict}
Хранится в `widgets.json` в LOG_DIR. `opts` — задел под персональные настройки
конкретного виджета (пока пустой словарь).
"""

import os

from config import LOG_DIR
from modules.json_file import read_json, write_json_atomic

_WIDGETS_FILE = os.path.join(LOG_DIR, "widgets.json")


def load_widgets() -> list[dict]:
    """Загружает список записей виджетов. Пусто при отсутствии/повреждении файла."""
    data = read_json(_WIDGETS_FILE)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_widgets(items: list[dict]):
    """Атомарно сохраняет список записей виджетов (через временный файл)."""
    try:
        write_json_atomic(_WIDGETS_FILE, items)
    except OSError:
        pass
