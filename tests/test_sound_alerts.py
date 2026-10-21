"""
Тесты звуковых сигналов (`modules/widget/alerts.SoundAlerts`) без звука.

Сигнал нормы звучит один раз на пересечение порога и молчит в нерабочий
день; тиканье — только в предупредительной фазе, не на нуле, не в нерабочий
день и не после нормы, если отсчёт остановлен настройкой. Сигналы зависят
только от данных: ни окна, ни мини-виджетов здесь нет.

Запуск: `python -m pytest tests/test_sound_alerts.py`
или как скрипт: `python tests/test_sound_alerts.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from modules.widget.alerts import SoundAlerts  # noqa: E402

_SETTINGS = {
    "SOUND_NOTIFICATION": True,
    "COUNTDOWN_TICK_SOUND": True,
    "STOP_COUNTDOWN_AT_RECOMMENDED": False,
    "RECOMMENDED_ACTIVITY_THRESHOLD": 80,
    "COUNTDOWN_WARNING_SECONDS": 30,
}


def _alerts(**overrides) -> tuple[SoundAlerts, list[str]]:
    """SoundAlerts с записью проигранного и заданными настройками config."""
    for key, value in {**_SETTINGS, **overrides}.items():
        setattr(config, key, value)
    played: list[str] = []
    alerts = SoundAlerts(
        play_goal=lambda: played.append("goal"),
        play_tick=lambda: played.append("tick"),
    )
    return alerts, played


def _stats(percent: float, working: bool = True) -> dict:
    return {"activity_percent": percent, "is_working_day": working}


def test_goal_plays_once_per_crossing():
    alerts, played = _alerts()
    alerts.update(_stats(50))
    alerts.update(_stats(85))
    alerts.update(_stats(90))
    assert played == ["goal"]
    # Упали ниже порога и снова поднялись — новое достижение, новый сигнал.
    alerts.update(_stats(70))
    alerts.update(_stats(81))
    assert played == ["goal", "goal"]


def test_goal_silent_when_disabled():
    alerts, played = _alerts(SOUND_NOTIFICATION=False)
    alerts.update(_stats(95))
    assert played == []


def test_goal_silent_on_day_off():
    alerts, played = _alerts()
    alerts.update(_stats(95, working=False))
    assert played == []


def test_tick_only_in_warning_phase():
    alerts, played = _alerts()
    alerts.update(_stats(50))
    for remaining in (None, 120, 31, 0):
        alerts.tick_second(remaining)
    assert played == []
    alerts.tick_second(30)
    alerts.tick_second(1)
    assert played == ["tick", "tick"]


def test_tick_before_first_stats():
    # Первые stats приходят не сразу — до них день считается рабочим.
    alerts, played = _alerts()
    alerts.tick_second(10)
    assert played == ["tick"]


def test_tick_silent_when_disabled_or_no_warning():
    alerts, played = _alerts(COUNTDOWN_TICK_SOUND=False)
    alerts.tick_second(10)
    alerts, played_no_warning = _alerts(COUNTDOWN_WARNING_SECONDS=0)
    alerts.tick_second(10)
    assert played == [] and played_no_warning == []


def test_tick_silent_on_day_off():
    alerts, played = _alerts()
    alerts.update(_stats(50, working=False))
    alerts.tick_second(10)
    assert played == []


def test_tick_after_goal_depends_on_stop_setting():
    alerts, played = _alerts(SOUND_NOTIFICATION=False, STOP_COUNTDOWN_AT_RECOMMENDED=True)
    alerts.update(_stats(90))
    alerts.tick_second(10)
    assert played == []

    alerts, played = _alerts(SOUND_NOTIFICATION=False, STOP_COUNTDOWN_AT_RECOMMENDED=False)
    alerts.update(_stats(90))
    alerts.tick_second(10)
    assert played == ["tick"]


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
