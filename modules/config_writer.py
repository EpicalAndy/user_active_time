"""
Запись настроек: в пользовательский config.py на диске и в модуль config в памяти.

Диалог настроек (`settings_dialog`) собирает значения с контролов в плоский
словарь `values` и отдаёт его сюда — окно ничего не знает ни о регулярках,
ни о том, какие атрибуты config читаются динамически. Обе половины
принимают один и тот же словарь, поэтому файл и память не расходятся.

Формат `values` — см. `SettingsDialog._collect_values`: ключи в snake_case,
`metrics` — {АТРИБУТ: bool}, `work_hours` — {день: часы}, `tools` —
{АТРИБУТ: значение} по схемам инструментов.
"""

import re

import config
from bootstrap import USER_CONFIG_PATH
from constants import ENCODING
from modules import theme
from modules.tools.spec import SETTING_BOOL, SETTING_TEXT

# Порядок дней в блоке WORK_HOURS_BY_DAY — как в шаблоне config.py.
WORK_DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _read(path: str) -> str:
    with open(path, "r", encoding=ENCODING) as f:
        return f.read()


def _write(path: str, content: str):
    with open(path, "w", encoding=ENCODING) as f:
        f.write(content)


def write_config_file(values: dict, tool_specs: list[dict], path: str = USER_CONFIG_PATH):
    """Переписывает значения в пользовательском config.py.

    Файл правится текстом, построчными заменами по регуляркам, а не
    генерируется заново: так остаются комментарии и структура шаблона.
    Строка параметра обязана существовать — за это отвечает bootstrap,
    который при старте досыпает в пользовательский конфиг новые параметры
    из проектного шаблона.

    `tool_specs` — схемы настроек инструментов (`SETTINGS` из реестра):
    строки пишутся в кавычках, числа и флаги как есть.
    """
    content = render_config(_read(path), values, tool_specs)
    _write(path, content)


def render_config(content: str, values: dict, tool_specs: list[dict]) -> str:
    """Текст config.py с подставленными значениями (чистая функция — для тестов)."""
    # Таймеры
    content = re.sub(
        r"^INPUT_ACTIVITY_TIMEOUT\s*=\s*.+$",
        f"INPUT_ACTIVITY_TIMEOUT = {values['input_activity_timeout']}",
        content, flags=re.MULTILINE,
    )
    content = re.sub(
        r"^COUNTDOWN_WARNING_SECONDS\s*=\s*.+$",
        f"COUNTDOWN_WARNING_SECONDS = {values['countdown_warning_seconds']}",
        content, flags=re.MULTILINE,
    )
    content = re.sub(
        r"^SOUND_NOTIFICATION\s*=\s*.+$",
        f"SOUND_NOTIFICATION = {values['sound_notification']}",
        content, flags=re.MULTILINE,
    )
    content = re.sub(
        r"^COUNTDOWN_TICK_SOUND\s*=\s*.+$",
        f"COUNTDOWN_TICK_SOUND = {values['countdown_tick_sound']}",
        content, flags=re.MULTILINE,
    )
    content = re.sub(
        r"^STOP_COUNTDOWN_AT_RECOMMENDED\s*=\s*.+$",
        f"STOP_COUNTDOWN_AT_RECOMMENDED = {values['stop_countdown_at_recommended']}",
        content, flags=re.MULTILINE,
    )
    content = re.sub(
        r"^WIDGET_PROGRESS_HIGHLIGHT\s*=\s*.+$",
        f"WIDGET_PROGRESS_HIGHLIGHT = {values['widget_progress_highlight']}",
        content, flags=re.MULTILINE,
    )
    content = re.sub(
        r"^TRACK_MOUSE_MOVE\s*=\s*.+$",
        f"TRACK_MOUSE_MOVE = {values['track_mouse_move']}",
        content, flags=re.MULTILINE,
    )

    # Настройки инструментов — по схеме из реестра: строки пишутся
    # в кавычках, числа и флаги как есть.
    for spec in tool_specs:
        key = spec["key"]
        value = values["tools"][key]
        if spec.get("kind", SETTING_BOOL) == SETTING_TEXT:
            replacement = f'{key} = "{value}"'
        else:
            replacement = f"{key} = {value}"
        content = re.sub(
            "^" + key + r"\s*=\s*.+$",
            replacement,
            content, flags=re.MULTILINE,
        )

    # Тема оформления (строковое значение — в кавычках)
    content = re.sub(
        r"^THEME\s*=\s*.+$",
        f'THEME = "{values["theme"]}"',
        content, flags=re.MULTILINE,
    )

    # Режим недельной полосы — тоже строка
    content = re.sub(
        r"^WIDGET_WEEK_MODE\s*=\s*.+$",
        f'WIDGET_WEEK_MODE = "{values["week_mode"]}"',
        content, flags=re.MULTILINE,
    )

    # Пороги
    for key, attr in (
        ("recommended_activity_threshold", "RECOMMENDED_ACTIVITY_THRESHOLD"),
        ("min_activity_threshold", "MIN_ACTIVITY_THRESHOLD"),
        ("recommended_work_time_threshold", "RECOMMENDED_WORK_TIME_THRESHOLD"),
        ("min_work_time_threshold", "MIN_WORK_TIME_THRESHOLD"),
        ("free_time_warning_percent", "FREE_TIME_WARNING_PERCENT"),
    ):
        content = re.sub(
            rf"^{attr}\s*=\s*.+$",
            f"{attr} = {values[key]}",
            content, flags=re.MULTILINE,
        )

    # Метрики
    for attr, val in values["metrics"].items():
        content = re.sub(
            rf"^{attr}\s*=\s*.+$",
            f"{attr} = {val}",
            content, flags=re.MULTILINE,
        )

    # Рабочие часы — заменяем весь блок WORK_HOURS_BY_DAY
    hours = values["work_hours"]
    new_block = "WORK_HOURS_BY_DAY = {\n"
    for key in WORK_DAY_KEYS:
        v = hours[key]
        formatted = str(int(v)) if v == int(v) else f"{v:.2f}"
        new_block += f'    "{key}": {formatted},\n'
    new_block += "}"
    content = re.sub(
        r"^WORK_HOURS_BY_DAY\s*=\s*\{[^}]+\}",
        new_block,
        content, flags=re.MULTILINE | re.DOTALL,
    )

    # Перерыв
    content = re.sub(
        r"^BREAK_MINUTES\s*=\s*.+$",
        f"BREAK_MINUTES = {values['break_minutes']}",
        content, flags=re.MULTILINE,
    )

    return content


def apply_runtime(values: dict):
    """Обновляет атрибуты модуля config в памяти — то же, что записано в файл."""
    config.SOUND_NOTIFICATION = values["sound_notification"]
    config.COUNTDOWN_TICK_SOUND = values["countdown_tick_sound"]
    config.STOP_COUNTDOWN_AT_RECOMMENDED = values["stop_countdown_at_recommended"]
    config.WIDGET_PROGRESS_HIGHLIGHT = values["widget_progress_highlight"]
    config.TRACK_MOUSE_MOVE = values["track_mouse_move"]
    config.INPUT_ACTIVITY_TIMEOUT = values["input_activity_timeout"]
    config.COUNTDOWN_WARNING_SECONDS = values["countdown_warning_seconds"]
    config.RECOMMENDED_ACTIVITY_THRESHOLD = values["recommended_activity_threshold"]
    config.MIN_ACTIVITY_THRESHOLD = values["min_activity_threshold"]
    config.RECOMMENDED_WORK_TIME_THRESHOLD = values["recommended_work_time_threshold"]
    config.MIN_WORK_TIME_THRESHOLD = values["min_work_time_threshold"]
    config.FREE_TIME_WARNING_PERCENT = values["free_time_warning_percent"]
    # Настройки инструментов: значения кладём в config, а перечитать их
    # инструменты просит сам виджет (ActivityWidget._open_settings →
    # tools.refresh_tools) — остальное читается динамически по месту.
    for key, value in values["tools"].items():
        setattr(config, key, value)
    # Режим читается полосой на каждом обновлении — применится со следующим тиком.
    config.WIDGET_WEEK_MODE = values["week_mode"]
    for attr, val in values["metrics"].items():
        setattr(config, attr, val)
    for key, val in values["work_hours"].items():
        config.WORK_HOURS_BY_DAY[key] = val
    config.BREAK_MINUTES = values["break_minutes"]
    # Тема: обновляем config и перепривязываем палитру theme.COLOR_*.
    # Окна, открытые после этого, отрисуются в новой теме; постоянный
    # виджет перекрасит себя сам (ActivityWidget._apply_theme).
    config.THEME = values["theme"]
    theme.set_theme(values["theme"])
