"""
Данные недельной полосы активности.

Отвечает на один вопрос: «какие семь дней показывать и что известно про
каждый». Отрисовка — в modules/widget/week_strip.py, здесь только tkinter-
независимые вычисления (так их можно проверить тестами без окна).

Два режима недели (config.WIDGET_WEEK_MODE):
    calendar — календарная, Пн–Вс текущей недели; дни после сегодня ещё
        не наступили и показываются пустыми;
    rolling  — скользящая, последние семь дней, сегодня — крайний справа.
Клеток всегда семь: в обоих режимах ширина полосы одинаковая и не «дышит»
от того, какой сегодня день недели.

Источники данных разные для сегодня и для прошлого:
    сегодня — живые stats виджета (дневной JSON пишется чекпоинтом раз в
        CHECKPOINT_INTERVAL и отстаёт от того, что виджет показывает строкой
        выше — брать клетку из файла значило бы противоречить себе);
    прошлые дни — дневные JSON-отчёты, те же, что кормят тепловую карту.

Вид клетки (`kind`) отделяет «плохо поработал» от «нечего показывать»:
    KIND_DATA    — есть данные, красится по проценту активности;
    KIND_NO_DATA — рабочий день без отчёта (приложение не работало);
    KIND_DAY_OFF — рабочих часов 0: нормы нет, 0% здесь не провал;
    KIND_FUTURE  — день ещё не наступил (бывает только в календарном режиме).
"""

import datetime

from modules.period_report import _read_day_metrics, percent
from utility import get_work_hours

# Значения config.WIDGET_WEEK_MODE.
WEEK_MODE_CALENDAR = "calendar"
WEEK_MODE_ROLLING = "rolling"

# Виды клетки (см. шапку модуля).
KIND_DATA = "data"
KIND_NO_DATA = "no_data"
KIND_DAY_OFF = "day_off"
KIND_FUTURE = "future"

WEEK_LENGTH = 7


def week_dates(today: datetime.date, mode: str) -> list[datetime.date]:
    """Семь дат полосы слева направо.

    Неизвестный режим трактуется как календарный: `widgets`-настройки правятся
    руками, и опечатка в режиме не должна ронять виджет.
    """
    if mode == WEEK_MODE_ROLLING:
        start = today - datetime.timedelta(days=WEEK_LENGTH - 1)
    else:
        start = today - datetime.timedelta(days=today.weekday())
    return [start + datetime.timedelta(days=i) for i in range(WEEK_LENGTH)]


def build_week(
    today: datetime.date,
    mode: str,
    today_stats: dict | None = None,
    read_metrics=_read_day_metrics,
) -> list[dict]:
    """Семь клеток полосы: вид, проценты и время по каждому дню.

    `today_stats` — тот же словарь, что получает тело виджета; None означает
    «живых данных нет», и сегодня читается из отчёта, как обычный день.
    `read_metrics` вынесен параметром ради тестов: подменив его, можно
    разложить неделю без файлов на диске.
    """
    return [
        _build_cell(date, today, mode, today_stats, read_metrics)
        for date in week_dates(today, mode)
    ]


def _build_cell(
    date: datetime.date,
    today: datetime.date,
    mode: str,
    today_stats: dict | None,
    read_metrics,
) -> dict:
    cell = {
        "date": date,
        "is_today": date == today,
        "kind": KIND_NO_DATA,
        "activity_percent": None,
        "work_percent": None,
        "active_seconds": 0,
        "work_seconds": 0,
    }

    if date > today:
        cell["kind"] = KIND_FUTURE
        return cell

    day_off = get_work_hours(date) == 0

    if date == today and today_stats is not None:
        # Нерабочий день stats сворачивает до {"is_working_day": False} —
        # цифр в нём нет, и клетка остаётся выходной без обращения к файлу.
        if today_stats.get("is_working_day", True):
            _fill_from_stats(cell, today_stats)
            return cell
        cell["kind"] = KIND_DAY_OFF
        return cell

    metrics = read_metrics(date)
    if metrics is not None:
        cell["active_seconds"] = metrics["active_seconds"]
        cell["work_seconds"] = metrics["total_work_seconds"]

    # Выходной остаётся выходным, даже если в этот день что-то отработано:
    # нормы у него нет, а значит нет и процентов — красить не по чему. Время
    # при этом показываем честно, оно уже прочитано выше.
    if day_off:
        cell["kind"] = KIND_DAY_OFF
        return cell
    if metrics is not None:
        cell["kind"] = KIND_DATA
        cell["activity_percent"] = percent(
            metrics["active_seconds"], metrics["activity_norm_seconds"],
        )
        cell["work_percent"] = percent(
            metrics["total_work_seconds"], metrics["max_work_seconds"],
        )
    return cell


def _fill_from_stats(cell: dict, stats: dict):
    """Сегодняшняя клетка из живых stats виджета."""
    max_work = stats.get("max_work_seconds", 0)
    full_day = stats.get("full_day_seconds", 0)
    cell["kind"] = KIND_DATA
    cell["active_seconds"] = stats.get("active_seconds", 0)
    cell["work_seconds"] = full_day
    cell["activity_percent"] = stats.get("activity_percent")
    cell["work_percent"] = percent(full_day, max_work)
