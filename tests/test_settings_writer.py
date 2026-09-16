"""
Тесты записи настроек в текст config.py (`modules/settings/writer.render_config`).

Логика раньше жила внутри диалога настроек и без окна не проверялась.
Проверяется, что подстановка идёт построчно (комментарии и незнакомые строки
остаются как были), строки пишутся в кавычках, блок WORK_HOURS_BY_DAY
переписывается целиком, а дробные часы не теряют точность.

Запуск: `python -m pytest tests/test_settings_writer.py`
или как скрипт: `python tests/test_settings_writer.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.settings.writer import WORK_DAY_KEYS, render_config  # noqa: E402
from modules.tools.spec import SETTING_BOOL, SETTING_TEXT  # noqa: E402

TEMPLATE = '''# Таймаут
DEFAULT_INPUT_ACTIVITY_TIMEOUT = 300
COUNTDOWN_WARNING_SECONDS = 60
SOUND_NOTIFICATION = True
COUNTDOWN_TICK_SOUND = False
STOP_COUNTDOWN_AT_RECOMMENDED = False
WIDGET_PROGRESS_HIGHLIGHT = True
TRACK_MOUSE_MOVE = True
INPUT_LOCK_HOTKEY = "ctrl+alt+l"
INPUT_LOCK_SHOW_HINT = True
THEME = "dark"
WIDGET_WEEK_MODE = "calendar"
RECOMMENDED_ACTIVITY_THRESHOLD = 80
MIN_ACTIVITY_THRESHOLD = 70
RECOMMENDED_WORK_TIME_THRESHOLD = 100
MIN_WORK_TIME_THRESHOLD = 80
FREE_TIME_WARNING_PERCENT = 20
WIDGET_SHOW_ACTIVE_TIME = True
WIDGET_SHOW_SESSION_COUNT = False
WORK_HOURS_BY_DAY = {
    "monday": 8,
    "tuesday": 8,
    "wednesday": 8,
    "thursday": 8,
    "friday": 8,
    "saturday": 0,
    "sunday": 0,
}
INPUT_ACTIVITY_TIMEOUT_BY_DAY = {
    "monday": 300,
    "tuesday": 300,
    "wednesday": 300,
    "thursday": 300,
    "friday": 300,
    "saturday": 300,
    "sunday": 300,
}
BREAK_MINUTES = 30
UNTOUCHED = "stays"
'''

TOOL_SPECS = [
    {"key": "INPUT_LOCK_HOTKEY", "kind": SETTING_TEXT},
    {"key": "INPUT_LOCK_SHOW_HINT", "kind": SETTING_BOOL},
]


def values(**overrides) -> dict:
    base = {
        "work_hours": {key: 8 for key in WORK_DAY_KEYS},
        "input_timeouts": {key: 300 for key in WORK_DAY_KEYS},
        "break_minutes": 45,
        "metrics": {"WIDGET_SHOW_ACTIVE_TIME": False, "WIDGET_SHOW_SESSION_COUNT": True},
        "theme": "light",
        "week_mode": "rolling",
        "countdown_warning_seconds": 30,
        "sound_notification": False,
        "countdown_tick_sound": True,
        "stop_countdown_at_recommended": True,
        "widget_progress_highlight": False,
        "track_mouse_move": False,
        "recommended_activity_threshold": 85,
        "min_activity_threshold": 75,
        "recommended_work_time_threshold": 95,
        "min_work_time_threshold": 70,
        "free_time_warning_percent": 0,
        "tools": {"INPUT_LOCK_HOTKEY": "win+l", "INPUT_LOCK_SHOW_HINT": False},
    }
    base.update(overrides)
    return base


def lines_of(text: str) -> dict:
    """{ИМЯ: текст значения} по строкам вида NAME = value."""
    out = {}
    for line in text.splitlines():
        if " = " in line and not line.startswith(" "):
            name, value = line.split(" = ", 1)
            out[name] = value
    return out


def test_scalars_are_replaced_line_by_line():
    got = lines_of(render_config(TEMPLATE, values(), TOOL_SPECS))
    assert got["DEFAULT_INPUT_ACTIVITY_TIMEOUT"] == "300"
    assert got["SOUND_NOTIFICATION"] == "False"
    assert got["RECOMMENDED_ACTIVITY_THRESHOLD"] == "85"
    assert got["FREE_TIME_WARNING_PERCENT"] == "0"
    assert got["WIDGET_SHOW_ACTIVE_TIME"] == "False"
    assert got["WIDGET_SHOW_SESSION_COUNT"] == "True"
    assert got["BREAK_MINUTES"] == "45"


def test_strings_are_quoted():
    got = lines_of(render_config(TEMPLATE, values(), TOOL_SPECS))
    assert got["THEME"] == '"light"'
    assert got["WIDGET_WEEK_MODE"] == '"rolling"'
    assert got["INPUT_LOCK_HOTKEY"] == '"win+l"'
    assert got["INPUT_LOCK_SHOW_HINT"] == "False"


def test_comments_and_unknown_lines_survive():
    out = render_config(TEMPLATE, values(), TOOL_SPECS)
    assert out.startswith("# Таймаут\n")
    assert 'UNTOUCHED = "stays"' in out


def test_work_hours_block_is_rewritten_in_template_order():
    hours = {key: 8 for key in WORK_DAY_KEYS}
    hours["friday"] = 7.5
    hours["saturday"] = 0
    out = render_config(TEMPLATE, values(work_hours=hours), TOOL_SPECS)
    block = out[out.index("WORK_HOURS_BY_DAY = {"):]
    block = block[:block.index("}") + 1]
    assert block == (
        "WORK_HOURS_BY_DAY = {\n"
        '    "monday": 8,\n'
        '    "tuesday": 8,\n'
        '    "wednesday": 8,\n'
        '    "thursday": 8,\n'
        '    "friday": 7.50,\n'
        '    "saturday": 0,\n'
        '    "sunday": 8,\n'
        "}"
    )


def test_timeout_by_day_block_is_rewritten():
    timeouts = {key: 300 for key in WORK_DAY_KEYS}
    timeouts["monday"] = 180
    timeouts["friday"] = 600
    out = render_config(TEMPLATE, values(input_timeouts=timeouts), TOOL_SPECS)
    block = out[out.index("INPUT_ACTIVITY_TIMEOUT_BY_DAY = {"):]
    block = block[:block.index("}") + 1]
    expected = [
        "INPUT_ACTIVITY_TIMEOUT_BY_DAY = {",
        '    "monday": 180,',
        '    "tuesday": 300,',
        '    "wednesday": 300,',
        '    "thursday": 300,',
        '    "friday": 600,',
        '    "saturday": 300,',
        '    "sunday": 300,',
        "}",
    ]
    assert block.splitlines() == expected
    # Дефолт для дня без записи блоком не задет.
    assert lines_of(out)["DEFAULT_INPUT_ACTIVITY_TIMEOUT"] == "300"


def test_rendering_is_idempotent():
    """Повторная запись тех же значений не меняет файл — иначе он бы «дрейфовал»."""
    once = render_config(TEMPLATE, values(), TOOL_SPECS)
    twice = render_config(once, values(), TOOL_SPECS)
    assert once == twice


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
