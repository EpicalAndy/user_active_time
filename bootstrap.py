"""
Инициализация пользовательского config.py.

config.py в проекте — это шаблон с дефолтными значениями. При каждом запуске
пользовательский конфиг пересобирается из шаблона: значения присваиваний
верхнего уровня берутся из существующего пользовательского конфига (если
он есть), а структура, комментарии и новые параметры — из проектного
шаблона. Так новые параметры автоматически попадают в рабочий конфиг без
потери уже настроенных значений.

Должен быть вызван из main.py до импортов, читающих config.
"""

import ast
import os
import sys

# Путь должен совпадать с LOG_DIR в config.py. Дублируется здесь намеренно:
# bootstrap решает, из какого файла грузить config, поэтому LOG_DIR ещё нельзя
# импортировать.
USER_LOG_DIR = os.path.join(os.path.expanduser("~"), "active_time")
USER_CONFIG_PATH = os.path.join(USER_LOG_DIR, "config.py")

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG_PATH = os.path.join(_PROJECT_DIR, "config.py")
_ENCODING = "utf-8"


def setup_user_config():
    """Создаёт/обновляет пользовательский config.py и подключает его как `config`."""
    os.makedirs(USER_LOG_DIR, exist_ok=True)

    with open(_DEFAULT_CONFIG_PATH, "r", encoding=_ENCODING) as f:
        default_text = f.read()

    user_text = None
    if os.path.exists(USER_CONFIG_PATH):
        with open(USER_CONFIG_PATH, "r", encoding=_ENCODING) as f:
            user_text = f.read()

    try:
        merged = _merge_config(default_text, user_text)
    except SyntaxError as e:
        # Не затираем повреждённый пользовательский конфиг — пусть импорт упадёт
        # с понятной ошибкой, чтобы пользователь мог поправить файл.
        print(f"[BOOTSTRAP] Не удалось разобрать пользовательский конфиг ({e}); миграция пропущена.")
    else:
        if user_text is None:
            _atomic_write(USER_CONFIG_PATH, merged)
            print(f"[BOOTSTRAP] Создан пользовательский конфиг: {USER_CONFIG_PATH}")
        elif merged != user_text:
            _atomic_write(USER_CONFIG_PATH, merged)
            print(f"[BOOTSTRAP] Конфиг обновлён под актуальные дефолты: {USER_CONFIG_PATH}")

    if USER_LOG_DIR not in sys.path:
        sys.path.insert(0, USER_LOG_DIR)


def _merge_config(template_text: str, user_text: str | None) -> str:
    """Вставляет пользовательские значения в шаблон.

    Берёт текст дефолтов как основу: структура, комментарии и набор параметров
    остаются из проекта. Для имён, присутствующих в пользовательском конфиге,
    значение в шаблоне заменяется на пользовательское. Имена, которых нет
    в дефолтах, отбрасываются.
    """
    if not user_text:
        return template_text

    user_values = _extract_top_level_values(user_text)
    if not user_values:
        return template_text

    template_bytes = template_text.encode(_ENCODING)
    template_tree = ast.parse(template_text)
    line_offsets = _line_offsets_bytes(template_bytes)

    # Готовим замены и применяем с конца, чтобы смещения слева не съезжали.
    replacements: list[tuple[int, int, bytes]] = []
    for node in template_tree.body:
        name = _assign_name(node)
        if name is None or name not in user_values:
            continue
        value = node.value
        start = line_offsets[value.lineno - 1] + value.col_offset
        end = line_offsets[value.end_lineno - 1] + value.end_col_offset
        replacements.append((start, end, user_values[name].encode(_ENCODING)))

    replacements.sort(reverse=True)
    result = template_bytes
    for start, end, new_bytes in replacements:
        result = result[:start] + new_bytes + result[end:]
    return result.decode(_ENCODING)


def _extract_top_level_values(text: str) -> dict[str, str]:
    """Возвращает {имя: исходный текст значения} для присваиваний верхнего уровня."""
    tree = ast.parse(text)
    values: dict[str, str] = {}
    for node in tree.body:
        name = _assign_name(node)
        if name is None:
            continue
        segment = ast.get_source_segment(text, node.value)
        if segment is not None:
            values[name] = segment
    return values


def _assign_name(node: ast.stmt) -> str | None:
    """Имя цели для простого `NAME = ...` на верхнем уровне; иначе None."""
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    if not isinstance(target, ast.Name):
        return None
    return target.id


def _line_offsets_bytes(data: bytes) -> list[int]:
    """Смещения начала каждой строки в байтах (1-я строка — индекс 0).

    AST col_offset/end_col_offset считаются в UTF-8 байтах, поэтому для подмены
    значений в тексте с не-ASCII символами работаем с байтовым представлением.
    """
    offsets = [0]
    for i, ch in enumerate(data):
        if ch == 0x0A:  # '\n'
            offsets.append(i + 1)
    return offsets


def _atomic_write(path: str, content: str):
    """Атомарная запись через временный файл рядом."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding=_ENCODING) as f:
        f.write(content)
    os.replace(tmp_path, path)
