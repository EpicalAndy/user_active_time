"""
Тесты «живой» статистики (modules/session_monitor/stats.py).

Проверяют главное свойство `get_current_stats`: только что закрытый гэп простоя
виден в метриках и на таймлайне СРАЗУ, не дожидаясь checkpoint'а. Гэп попадает
в state.json только при checkpoint (раз в `CHECKPOINT_INTERVAL` секунд), поэтому
до этого момента его нужно брать из буфера монитора ввода — иначе простой на
минуту-другую исчезает из статистики и с круга таймлайна.

Запуск: `python -m pytest tests/test_stats_pending_idle.py`
или как скрипт: `python tests/test_stats_pending_idle.py`.
"""

import datetime
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import events_monitor  # noqa: E402
from modules.session_monitor import stats  # noqa: E402
from utility import format_date_key  # noqa: E402

DAY = datetime.date(2026, 6, 21)
NOW = datetime.datetime.combine(DAY, datetime.time(12, 0))
TIMEOUT = 300


def dt(h, m=0, s=0):
    return datetime.datetime.combine(DAY, datetime.time(h, m, s))


class _FrozenDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


class _FrozenDate(datetime.date):
    @classmethod
    def today(cls):
        return DAY


def _day_state():
    """Запись дня: логин в 09:00, сохранённых интервалов ещё нет."""
    return {
        "active_seconds": 0,
        "session_count": 1,
        "first_login": "09:00:00",
        "last_logout": None,
        "sessions": [],
        "idle": [],
        "legacy_base_seconds": 0,
        "log_entries": [],
    }


def _collect(pending_gaps, stored_idle=()):
    """Считает stats при заданных буфере монитора и сохранённых гэпах.

    Сессия живая: началась в 09:00, «сейчас» — 12:00 (часы заморожены).
    """
    day_state = _day_state()
    day_state["idle"] = [
        {"from": s.strftime("%Y-%m-%d %H:%M:%S"), "to": e.strftime("%Y-%m-%d %H:%M:%S")}
        for s, e in stored_idle
    ]
    state = {format_date_key(DAY): day_state}

    saved = {
        "datetime": stats.datetime,
        "load_state": stats.load_state,
        "get_work_hours": stats.get_work_hours,
        "get_activity_norm_hours": stats.get_activity_norm_hours,
        "get_break_hours": stats.get_break_hours,
        "session_start_time": stats.session.session_start_time,
        "peek": events_monitor.peek_idle_gaps,
        "open_idle": events_monitor.get_open_idle,
        "timeout": config.INPUT_ACTIVITY_TIMEOUT,
    }
    try:
        stats.datetime = types.SimpleNamespace(
            datetime=_FrozenDateTime, date=_FrozenDate, timedelta=datetime.timedelta,
        )
        stats.load_state = lambda: state
        stats.get_work_hours = lambda _d: 8.0
        stats.get_activity_norm_hours = lambda _d: 8.0
        stats.get_break_hours = lambda _d: 0.0
        stats.session.session_start_time = dt(9)
        events_monitor.peek_idle_gaps = lambda: list(pending_gaps)
        events_monitor.get_open_idle = lambda: None
        config.INPUT_ACTIVITY_TIMEOUT = TIMEOUT
        return stats.get_current_stats()
    finally:
        stats.datetime = saved["datetime"]
        stats.load_state = saved["load_state"]
        stats.get_work_hours = saved["get_work_hours"]
        stats.get_activity_norm_hours = saved["get_activity_norm_hours"]
        stats.get_break_hours = saved["get_break_hours"]
        stats.session.session_start_time = saved["session_start_time"]
        events_monitor.peek_idle_gaps = saved["peek"]
        events_monitor.get_open_idle = saved["open_idle"]
        config.INPUT_ACTIVITY_TIMEOUT = saved["timeout"]


def _inactive_segments(result):
    """Отрезки простоя таймлайна в секундах от полуночи."""
    return [(s, e) for s, e, kind in result["timeline"]["segments"] if kind == "inactive"]


def test_no_idle_at_all():
    """Без простоя весь отрезок [логин, сейчас] активен."""
    result = _collect(pending_gaps=[])
    assert result["active_seconds"] == 3 * 3600
    assert _inactive_segments(result) == []


def test_pending_gap_counted_in_active_seconds():
    """Закрытый, но ещё не сохранённый гэп сразу вычитается из активного времени."""
    result = _collect(pending_gaps=[(dt(10), dt(11))])  # inactive = [10:05, 11:00]
    assert result["active_seconds"] == 3 * 3600 - 3300


def test_pending_gap_visible_on_timeline():
    """Тот же гэп сразу виден на таймлайне (иначе круг остаётся весь зелёный)."""
    result = _collect(pending_gaps=[(dt(10), dt(11))])
    assert _inactive_segments(result) == [(10 * 3600 + 300, 11 * 3600)]


def test_checkpoint_does_not_change_numbers():
    """Слив гэпа в state (checkpoint) не меняет ни метрику, ни таймлайн.

    До checkpoint'а гэп лежит в буфере монитора, после — в state.json.
    Картинка и цифры обязаны совпадать, иначе checkpoint виден глазом как
    скачок процента и появление/исчезание красного сектора.
    """
    gap = (dt(10), dt(11))
    before = _collect(pending_gaps=[gap])
    after = _collect(pending_gaps=[], stored_idle=[gap])
    assert before["active_seconds"] == after["active_seconds"]
    assert before["timeline"]["segments"] == after["timeline"]["segments"]


def test_short_pending_gap_does_not_cut_timeline():
    """Гэп короче таймаута простоем не считается — ни в цифрах, ни на круге."""
    result = _collect(pending_gaps=[(dt(10), dt(10, 3))])  # 180с < 300
    assert result["active_seconds"] == 3 * 3600
    assert _inactive_segments(result) == []


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
