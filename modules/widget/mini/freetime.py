"""
Мини-виджет «Свободное время» — кольцо остатка времени, которое можно НЕ быть
активным, оставаясь в норме.

Бюджет свободного времени за день = норма присутствия (рабочие часы из конфига
на текущий день) минус требуемая активность. Порогов активности два, поэтому и
бюджета два: до рекомендуемой нормы и до минимальной — второй больше.

За полное кольцо взят бюджет до **минимальной** нормы: так кольцо непрерывно
пустеет и по дороге меняет цвет, вместо того чтобы упереться в ноль на
рекомендуемой отметке и дальше стоять пустым.

- зелёное — рекомендуемая норма ещё достижима;
- жёлтое — рекомендуемую уже не вытянуть, минимальная ещё в запасе;
- красное (пустое кольцо, красный трек) — ушли в минус и по минимальной.

В центре по умолчанию остаток до **рекомендуемой** нормы — то самое «сколько
ещё можно расслабляться». Он и уходит в минус, показывая перерасход.
"""

from constants import WIDGET_CAPTION_FREE_TIME
from modules import theme
from utility import format_duration_signed
from ..body import free_time_color
from .ring import RingWidget


class FreeTimePieWidget(RingWidget):
    """Кольцо остатка свободного времени."""

    caption = WIDGET_CAPTION_FREE_TIME

    # --- Метрика ---

    def _fraction(self, stats: dict) -> float | None:
        """Доля оставшегося свободного времени от бюджета до минимальной нормы.

        Может быть отрицательной — кольцо тогда пустое, а цвет несёт трек.
        """
        budget_min = stats.get("free_budget_min_seconds", 0)
        if budget_min <= 0:
            return None
        return stats.get("free_remaining_min_seconds", 0) / budget_min * 100

    def _time_seconds(self, stats: dict) -> int:
        """В центре — остаток до рекомендуемой нормы (может быть отрицательным)."""
        return int(stats.get("free_remaining_seconds", 0))

    def _format_time(self, seconds: int) -> str:
        return format_duration_signed(seconds)

    # --- Цвет ---

    def _arc_color(self, pct: float, stats: dict) -> str:
        return free_time_color(
            stats.get("free_remaining_seconds", 0),
            stats.get("free_remaining_min_seconds", 0),
        )

    def _track_color(self, pct: float, stats: dict) -> str:
        """В минусе кольцо пустое, и единственный носитель цвета — трек."""
        if stats.get("free_remaining_min_seconds", 0) > 0:
            return theme.COLOR_LIGHT_GRAY
        return theme.COLOR_RED
