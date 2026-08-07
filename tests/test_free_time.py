"""
Тесты метрики «Свободное время».

Свободное время — сколько ещё можно НЕ быть активным, оставаясь в норме.
Бюджет за день = норма присутствия (рабочие часы из конфига) минус требуемая
активность; порогов активности два, поэтому и бюджета два — до рекомендуемой
нормы и до минимальной. Проверяются: арифметика бюджетов в stats, цветовое
правило и поведение мини-виджета (включая уход в минус).

Запуск: `python -m pytest tests/test_free_time.py`
или как скрипт: `python tests/test_free_time.py`.
"""

import datetime
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules import events_monitor, theme  # noqa: E402
from modules.session_monitor import stats  # noqa: E402
from modules.widget.body import free_time_color  # noqa: E402
from modules.widget.mini.freetime import FreeTimePieWidget  # noqa: E402
from utility import format_date_key, format_duration_signed  # noqa: E402

DAY = datetime.date(2026, 6, 21)
NOW = datetime.datetime.combine(DAY, datetime.time(12, 0))
TIMEOUT = 300

# Норма дня для тестов: присутствие 8ч, перерыв 30м → норма активности 7.5ч.
WORK_HOURS = 8.0
NORM_HOURS = 7.5
RECOMMENDED_PCT = 80  # → требуемая активность 6ч00м, бюджет свободного 2ч00м
MIN_PCT = 70          # → требуемая активность 5ч15м, бюджет свободного 2ч45м


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


def _collect(idle_gaps=()):
    """stats при живой сессии 09:00→12:00 и заданных сохранённых гэпах простоя."""
    day_state = {
        "active_seconds": 0,
        "session_count": 1,
        "first_login": "09:00:00",
        "last_logout": None,
        "sessions": [],
        "idle": [
            {"from": s.strftime("%Y-%m-%d %H:%M:%S"), "to": e.strftime("%Y-%m-%d %H:%M:%S")}
            for s, e in idle_gaps
        ],
        "legacy_base_seconds": 0,
        "log_entries": [],
    }
    state = {format_date_key(DAY): day_state}

    saved = {
        "datetime": stats.datetime,
        "load_state": stats.load_state,
        "work": stats.get_work_hours,
        "norm": stats.get_activity_norm_hours,
        "brk": stats.get_break_hours,
        "session_start_time": stats.session.session_start_time,
        "peek": events_monitor.peek_idle_gaps,
        "open_idle": events_monitor.get_open_idle,
        "timeout": config.INPUT_ACTIVITY_TIMEOUT,
        "recommended": config.RECOMMENDED_ACTIVITY_THRESHOLD,
        "minimum": config.MIN_ACTIVITY_THRESHOLD,
    }
    try:
        stats.datetime = types.SimpleNamespace(
            datetime=_FrozenDateTime, date=_FrozenDate, timedelta=datetime.timedelta,
        )
        stats.load_state = lambda: state
        stats.get_work_hours = lambda _d: WORK_HOURS
        stats.get_activity_norm_hours = lambda _d: NORM_HOURS
        stats.get_break_hours = lambda _d: 0.5
        stats.session.session_start_time = dt(9)
        events_monitor.peek_idle_gaps = list
        events_monitor.get_open_idle = lambda: None
        config.INPUT_ACTIVITY_TIMEOUT = TIMEOUT
        config.RECOMMENDED_ACTIVITY_THRESHOLD = RECOMMENDED_PCT
        config.MIN_ACTIVITY_THRESHOLD = MIN_PCT
        return stats.get_current_stats()
    finally:
        stats.datetime = saved["datetime"]
        stats.load_state = saved["load_state"]
        stats.get_work_hours = saved["work"]
        stats.get_activity_norm_hours = saved["norm"]
        stats.get_break_hours = saved["brk"]
        stats.session.session_start_time = saved["session_start_time"]
        events_monitor.peek_idle_gaps = saved["peek"]
        events_monitor.get_open_idle = saved["open_idle"]
        config.INPUT_ACTIVITY_TIMEOUT = saved["timeout"]
        config.RECOMMENDED_ACTIVITY_THRESHOLD = saved["recommended"]
        config.MIN_ACTIVITY_THRESHOLD = saved["minimum"]


def _widget():
    """Экземпляр мини-виджета без tk-окна: проверяемые методы окна не трогают."""
    w = object.__new__(FreeTimePieWidget)
    w.opts = {"center": "time"}
    return w


# --- Бюджеты в stats ---


def test_budgets_come_from_day_norm_and_thresholds():
    """Бюджет = норма присутствия минус требуемая активность, по двум порогам."""
    result = _collect()
    assert result["max_work_seconds"] == 8 * 3600
    # 8ч присутствия − 6ч00м (80% от 7.5ч) = 2ч00м
    assert result["free_budget_seconds"] == 2 * 3600
    # 8ч присутствия − 5ч15м (70% от 7.5ч) = 2ч45м
    assert result["free_budget_min_seconds"] == 2 * 3600 + 45 * 60


def test_no_idle_means_nothing_spent():
    """Без простоя свободное время не потрачено — остаток равен бюджету."""
    result = _collect()
    assert result["spent_free_seconds"] == 0
    assert result["free_remaining_seconds"] == result["free_budget_seconds"]
    assert result["free_remaining_min_seconds"] == result["free_budget_min_seconds"]


def test_idle_spends_free_time():
    """Присутствие 3ч, активность 2.5ч → потрачено 30м свободного."""
    result = _collect(idle_gaps=[(dt(10), dt(10, 35))])  # inactive = 30м
    assert result["full_day_seconds"] == 3 * 3600
    assert result["active_seconds"] == 3 * 3600 - 1800
    assert result["spent_free_seconds"] == 1800
    assert result["free_remaining_seconds"] == 2 * 3600 - 1800          # 1ч30м
    assert result["free_remaining_min_seconds"] == 2 * 3600 + 45 * 60 - 1800


def test_remaining_goes_negative_without_clamping():
    """Перерасход показывается минусом, а не нулём — иначе метрика врёт."""
    # Простой 2ч15м (плюс фора таймаута) съедает бюджет 2ч00м с перерасходом.
    result = _collect(idle_gaps=[(dt(9, 40), dt(11, 60 - 5))])
    assert result["free_remaining_seconds"] < 0
    assert result["free_remaining_min_seconds"] > 0  # минимальная норма ещё жива


# --- Цветовое правило ---


def test_color_green_while_recommended_reachable():
    assert free_time_color(1800, 7200) == theme.COLOR_GREEN


def test_color_yellow_between_thresholds():
    """Рекомендуемую уже не вытянуть, минимальная ещё в запасе."""
    assert free_time_color(-600, 2100) == theme.COLOR_YELLOW


def test_color_red_in_minus_by_minimum():
    assert free_time_color(-3600, -900) == theme.COLOR_RED


def test_color_boundary_zero_is_not_green():
    """Ровно нулевой остаток — это уже не «есть свободное время»."""
    assert free_time_color(0, 2700) == theme.COLOR_YELLOW
    assert free_time_color(0, 0) == theme.COLOR_RED


# --- Мини-виджет ---


def test_widget_fraction_scaled_by_min_budget():
    """Полное кольцо = бюджет до минимальной нормы."""
    w = _widget()
    stats_dict = {"free_budget_min_seconds": 9900, "free_remaining_min_seconds": 4950}
    assert w._fraction(stats_dict) == 50.0


def test_widget_fraction_none_without_budget():
    assert _widget()._fraction({"free_budget_min_seconds": 0}) is None


def test_widget_center_shows_remaining_to_recommended():
    """В центре — остаток до рекомендуемой нормы, со знаком."""
    w = _widget()
    stats_dict = {
        "free_budget_min_seconds": 9900,
        "free_remaining_min_seconds": 8100,
        "free_remaining_seconds": 5400,
    }
    assert w._center_text(stats_dict, True, 81.8) == "1ч 30м"
    stats_dict["free_remaining_seconds"] = -900
    assert w._center_text(stats_dict, True, 81.8) == "-0ч 15м"


def test_widget_track_turns_red_only_in_minus():
    """В минусе кольцо пустое, поэтому цвет берёт на себя трек."""
    w = _widget()
    assert w._track_color(50.0, {"free_remaining_min_seconds": 4950}) == theme.COLOR_LIGHT_GRAY
    assert w._track_color(-5.0, {"free_remaining_min_seconds": -300}) == theme.COLOR_RED


def test_widget_arc_color_follows_scale():
    w = _widget()
    green = {"free_remaining_seconds": 1800, "free_remaining_min_seconds": 7200}
    yellow = {"free_remaining_seconds": -600, "free_remaining_min_seconds": 2100}
    assert w._arc_color(45.0, green) == theme.COLOR_GREEN
    assert w._arc_color(21.0, yellow) == theme.COLOR_YELLOW


# --- Форматирование ---


def test_signed_duration_formatting():
    """На отрицательных обычный format_duration_short врёт из-за floor-деления."""
    assert format_duration_signed(5400) == "1ч 30м"
    # Часы не опускаем — так же, как format_duration_short во всём остальном UI.
    assert format_duration_signed(-900) == "-0ч 15м"
    assert format_duration_signed(-5400) == "-1ч 30м"
    assert format_duration_signed(0) == "0ч 0м"


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
