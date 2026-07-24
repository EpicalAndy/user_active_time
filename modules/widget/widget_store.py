"""
Персист реестра мини-виджетов рабочего стола.

Реестр — плоский список записей вида
    {"id": str, "type": str, "x": int, "y": int, "opts": dict}
Хранится в `widgets.json` в LOG_DIR. `opts` — задел под персональные настройки
конкретного виджета (пока пустой словарь).
"""

import json
import os

from config import LOG_DIR

_WIDGETS_FILE = os.path.join(LOG_DIR, "widgets.json")


def load_widgets() -> list[dict]:
    """Загружает список записей виджетов. Пусто при отсутствии/повреждении файла."""
    try:
        with open(_WIDGETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_widgets(items: list[dict]):
    """Атомарно сохраняет список записей виджетов (через временный файл)."""
    tmp_path = _WIDGETS_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, _WIDGETS_FILE)
    except IOError:
        pass
