"""
Цветовые шкалы и проценты метрик — общие для тела виджета, мини-виджетов,
недельной полосы и тепловой карты.

Без tkinter: только числа и цвета палитры (`theme.COLOR_*`, читаются в момент
вызова, поэтому смена темы подхватывается сама). Какая метрика по какой шкале
красится — описано в каталоге метрик (`metrics.Metric.scale`).
"""

import config
from modules import theme
from utility import PERCENT_DECIMALS, truncate_percent


def color_for_percent(
    pct: float, recommended: float, minimum: float,
    decimals: int = PERCENT_DECIMALS,
) -> str:
    """Зелёный/жёлтый/красный по двум порогам.

    Порог сверяется с тем числом, которое видит пользователь (усечённым до
    `decimals` знаков, см. truncate_percent), иначе цвет расходится с цифрой
    рядом: 79.96% печатается как «80.0%», а порог 80 ещё не взят. Мини-виджеты
    показывают процент без дробной части и передают decimals=0.
    """
    shown = truncate_percent(pct, decimals)
    if shown >= recommended:
        return theme.COLOR_GREEN
    if shown >= minimum:
        return theme.COLOR_YELLOW
    return theme.COLOR_RED


def free_time_color(remaining: int, budget: int) -> str:
    """Цвет метрики «свободное время» по остатку бюджета до рекомендуемой нормы.

    Шкала считается по тому же бюджету, который показывают цифры метрики
    (`free_remaining_seconds` и процент от `free_budget_seconds`), — иначе цвет
    расходится с числом рядом:
    - зелёный — остатка больше порога предупреждения;
    - жёлтый  — остаток не выше порога (`FREE_TIME_WARNING_PERCENT` % бюджета),
      свободное время заканчивается;
    - красный — остаток исчерпан (ноль или минус).

    Что просажена ещё и минимальная норма, цвет не показывает: это несёт
    геометрия кольца в мини-виджете (пустое кольцо + красный трек).
    """
    if remaining <= 0:
        return theme.COLOR_RED
    warning = config.FREE_TIME_WARNING_PERCENT
    if warning > 0 and budget > 0 and remaining <= budget * warning / 100:
        return theme.COLOR_YELLOW
    return theme.COLOR_GREEN


def work_time_percent(stats: dict) -> float | None:
    """% общего рабочего времени относительно нормы; None если нормы нет."""
    max_work = stats.get("max_work_seconds", 0)
    if max_work <= 0:
        return None
    return stats["full_day_seconds"] / max_work * 100


def remaining_time_percent(stats: dict) -> float | None:
    """% оставшегося до конца дня относительно нормы; None если нормы нет."""
    max_work = stats.get("max_work_seconds", 0)
    if max_work <= 0:
        return None
    remaining = max(0, stats.get("remaining_work_seconds", 0))
    return remaining / max_work * 100


def recommended_remaining_percent(stats: dict) -> float | None:
    """Сколько осталось добрать до рекомендуемой нормы, в % от неё.

    Считается как `recommended_remaining / recommended × 100`, где
    `recommended = activity_norm × RECOMMENDED_ACTIVITY_THRESHOLD / 100`,
    а `activity_norm` — рабочее время без перерыва.
    None — если нормы или порога нет.
    """
    activity_norm = stats.get("activity_norm_seconds", 0)
    threshold = config.RECOMMENDED_ACTIVITY_THRESHOLD
    if activity_norm <= 0 or threshold <= 0:
        return None
    recommended = activity_norm * threshold / 100
    remaining = max(0, stats.get("recommended_remaining_seconds", 0))
    return remaining / recommended * 100


def free_time_percent(stats: dict) -> float | None:
    """Остаток свободного времени в % от бюджета до рекомендуемой нормы.

    Знаменатель — тот же бюджет, к которому относится и само значение метрики
    (`free_remaining_seconds`), поэтому «30м (25%)» читается согласованно.
    Может быть отрицательным — это перерасход, а не ошибка. None — если бюджета
    нет вовсе (норма присутствия целиком уходит в требуемую активность).
    """
    budget = stats.get("free_budget_seconds", 0)
    if budget <= 0:
        return None
    return stats.get("free_remaining_seconds", 0) / budget * 100
