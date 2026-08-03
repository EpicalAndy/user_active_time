"""
Мини-виджет «Счётчик активности» — обратный отсчёт до перехода в неактивность.

Тот же счётчик, что в заголовке основного виджета, но отдельным кругом на
рабочем столе: сплошная заливка + «MM:SS» по центру.

- зелёный фон, обычный шрифт — до порога предупреждения (`COUNTDOWN_WARNING_SECONDS`);
- красный фон, жирный шрифт — порог пройден (и на нуле, когда пользователь
  уже неактивен) — как жирнеет счётчик в заголовке;
- серый фон и «—» — счётчик недоступен (нерабочий день, нет сессии,
  `INPUT_ACTIVITY_TIMEOUT = 0`).

Счётчик тикает каждую секунду, поэтому виджет не ждёт stats (они приходят раз в
`WIDGET_UPDATE_INTERVAL`), а сам читает `get_countdown_remaining()` на секундном
тике менеджера. Из stats нужен только контекст дня: рабочий ли он и выработана
ли норма.
"""

import tkinter as tk

import config
from constants import FONT_FAMILY, WIDGET_CAPTION_COUNTDOWN
from modules import theme
from modules.events_monitor import get_countdown_remaining
from .base import BaseMiniWidget
from .ring import PAD, SIZE

# Заполнитель на месте счётчика, когда норма выработана и отсчёт остановлен
# настройкой STOP_COUNTDOWN_AT_RECOMMENDED — тот же, что в заголовке.
_GOAL_PLACEHOLDER = "__:__"


class CountdownWidget(BaseMiniWidget):
    """Круг с обратным отсчётом до неактивности."""

    caption = WIDGET_CAPTION_COUNTDOWN

    def __init__(self, *args, **kwargs):
        # Контекст дня из последних stats — обновляется раз в минуту,
        # а перерисовка идёт каждую секунду.
        self._is_working_day = True
        self._goal_reached = False
        super().__init__(*args, **kwargs)

    # --- Отрисовка ---

    def _build(self):
        self._canvas = tk.Canvas(
            self.window, width=SIZE, height=SIZE,
            bg=theme.COLOR_DARK_BG, highlightthickness=0,
        )
        self._canvas.pack()
        self._caption_label = tk.Label(
            self.window, text=self.caption,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, 8),
        )
        self._caption_label.pack(fill=tk.X, pady=(0, 4))

    def update(self, stats: dict):
        self._is_working_day = stats.get("is_working_day", True)
        self._goal_reached = (
            stats.get("activity_percent", 0) >= config.RECOMMENDED_ACTIVITY_THRESHOLD
        )
        self._refresh()

    def tick_second(self):
        """Секундный тик менеджера — счётчику этого достаточно."""
        self._refresh()

    def _refresh(self):
        text, color, weight = self._state()
        self._draw(text, color, weight)

    def _state(self) -> tuple[str, str, str]:
        """(текст, цвет заливки, начертание) по текущему состоянию счётчика."""
        if not self._is_working_day:
            return "—", theme.COLOR_GRAY, "normal"

        # Норма выработана и отсчёт остановлен настройкой — как в заголовке:
        # зелёный заполнитель вместо цифр.
        if self._goal_reached and config.STOP_COUNTDOWN_AT_RECOMMENDED:
            return _GOAL_PLACEHOLDER, theme.COLOR_GREEN, "normal"

        remaining = get_countdown_remaining()
        if remaining is None:
            return "—", theme.COLOR_GRAY, "normal"

        minutes, secs = divmod(remaining, 60)
        text = f"{minutes:02d}:{secs:02d}"

        warning = config.COUNTDOWN_WARNING_SECONDS
        alert = remaining == 0 or (warning > 0 and remaining <= warning)
        if alert:
            return text, theme.COLOR_RED, "bold"
        return text, theme.COLOR_GREEN, "normal"

    def _draw(self, text: str, color: str, weight: str):
        c = self._canvas
        c.delete("all")
        c.configure(bg=theme.COLOR_DARK_BG)

        c.create_oval(
            PAD, PAD, SIZE - PAD, SIZE - PAD, fill=color, outline=color,
        )
        center = SIZE / 2
        c.create_text(
            center, center, text=text,
            fill=theme.COLOR_WHITE, font=(FONT_FAMILY, 18, weight),
        )
