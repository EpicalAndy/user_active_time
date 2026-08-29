"""
Тесты метрики «Достижение рекомендуемой нормы» (recommended_eta в stats.py).

Метрика отвечает на вопрос «во сколько я выйду на рекомендуемый порог
активности, если с этой секунды не простаивать». Отсюда её главные свойства,
которые здесь и проверяются:
- прогноз = сейчас + остаток до порога, поэтому каждая минута простоя двигает
  его ровно на минуту вперёд, а докинутое вручную время — назад;
- когда порог уже взят, показывается не прогноз, а фактический момент взятия,
  и он больше не «плывёт» со временем.

Цвет метрике даёт общая шкала активности (widget/body), поэтому здесь
проверяется только само значение.

Запуск: `python -m pytest tests/test_recommended_eta.py`
или как скрипт: `python tests/test_recommended_eta.py`.
"""

import datetime
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import events_monitor  # noqa: E402
from modules.session_monitor import journal, stats  # noqa: E402
from utility import format_date_key  # noqa: E402

DAY = datetime.date(2026, 6, 21)
TIMEOUT = 300


def dt(h, m=0, s=0):
    return datetime.datetime.combine(DAY, datetime.time(h, m, s))


def _frozen(now):
    class _FrozenDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    class _FrozenDate(datetime.date):
        @classmethod
        def today(cls):
            return DAY

    return _FrozenDateTime, _FrozenDate


def _collect(now=dt(12), work_hours=8.0, norm_hours=8.0, idle=(), manual=(), login="09:00:00"):
    """Считает stats: живая сессия с 09:00, часы заморожены на `now`.

    idle   — сохранённые гэпы простоя (пары datetime);
    manual — ручные интервалы активного времени (пары datetime).
    """
    log_entries = []
    for i, (start, end) in enumerate(manual):
        log_entries += list(journal.manual_lines(start, end, f"тест {i}"))

    day_state = {
        "active_seconds": 0,
        "session_count": 1,
        "first_login": login,
        "last_logout": None,
        "sessions": [],
        "idle": [
            {"from": s.strftime("%Y-%m-%d %H:%M:%S"), "to": e.strftime("%Y-%m-%d %H:%M:%S")}
            for s, e in idle
        ],
        "legacy_base_seconds": 0,
        "log_entries": log_entries,
    }
    state = {format_date_key(DAY): day_state}
    frozen_datetime, frozen_date = _frozen(now)

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
            datetime=frozen_datetime, date=frozen_date, timedelta=datetime.timedelta,
        )
        stats.load_state = lambda: state
        stats.get_work_hours = lambda _d: work_hours
        stats.get_activity_norm_hours = lambda _d: norm_hours
        stats.get_break_hours = lambda _d: work_hours - norm_hours
        stats.session.session_start_time = dt(9)
        events_monitor.peek_idle_gaps = lambda: []
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


def test_forecast_is_now_plus_remaining():
    """Порог 80% от 8ч = 6ч24м; за 3 часа активности остаток 3ч24м → 15:24."""
    result = _collect()
    assert result["recommended_remaining_seconds"] == 3 * 3600 + 24 * 60
    assert result["recommended_eta"] == "15:24"


def test_idle_pushes_forecast_forward():
    """Час простоя (минус таймаут-фора) сдвигает прогноз ровно на 55 минут."""
    base = _collect()
    delayed = _collect(idle=[(dt(10), dt(11))])  # неактивность = [10:05, 11:00]
    assert base["recommended_eta"] == "15:24"
    assert delayed["recommended_eta"] == "16:19"


def test_manual_time_pulls_forecast_back():
    """Докинутый вручную час приближает прогноз на тот же час."""
    result = _collect(manual=[(dt(8), dt(9))])
    assert result["recommended_eta"] == "14:24"


def test_reached_shows_actual_moment_not_forecast():
    """Порог взят — показываем факт: 80% от 2ч нормы набрались к 10:36.

    Прогноз на этот момент дал бы «сейчас» (12:00) — значение должно быть
    именно фактом, а не им.
    """
    result = _collect(work_hours=2.0, norm_hours=2.0)
    assert result["recommended_eta"] == "10:36"


def test_reached_moment_does_not_drift():
    """Факт достижения зафиксирован: позже по времени он не меняется."""
    at_noon = _collect(now=dt(12), work_hours=2.0, norm_hours=2.0)
    later = _collect(now=dt(16), work_hours=2.0, norm_hours=2.0)
    assert later["recommended_eta"] == at_noon["recommended_eta"] == "10:36"


def test_reached_moment_accounts_for_idle():
    """Простой отодвигает и фактический момент: 55 минут «неактивности» — 55 минут сдвига."""
    result = _collect(work_hours=2.0, norm_hours=2.0, idle=[(dt(10), dt(11))])
    assert result["recommended_eta"] == "11:31"


def test_forecast_may_land_past_end_of_day():
    """Прогноз не подрезается концом рабочего дня — он честно уходит за него.

    Присутствие 6ч (день 09:00–15:00) при норме активности 8ч: 80% за такой
    день не набрать, и метрика обязана это показать, а не приукрасить.
    """
    assert _collect(work_hours=6.0, norm_hours=8.0)["recommended_eta"] == "15:24"


def test_forecast_without_login():
    """Без первого логина (нет ни одной сохранённой сессии) прогноз всё равно есть."""
    assert _collect(login=None)["recommended_eta"] == "15:24"


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
