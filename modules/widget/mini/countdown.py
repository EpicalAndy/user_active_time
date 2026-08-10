"""
Мини-виджет «Счётчик активности» — обратный отсчёт до перехода в неактивность.

Тот же счётчик, что в заголовке основного виджета, но отдельным кругом на
рабочем столе: сплошная заливка + «MM:SS» по центру.

- зелёный фон, обычный шрифт — до порога предупреждения (`COUNTDOWN_WARNING_SECONDS`);
- красный фон, мигающее начертание (жирный ↔ обычный) — порог пройден: как
  мигает счётчик в заголовке основного виджета;
- красный фон, жирный шрифт без мигания — на нуле, когда пользователь уже
  неактивен (мигать больше не о чем);
- серый фон и «—» — счётчик недоступен (нерабочий день, нет сессии,
  `INPUT_ACTIVITY_TIMEOUT = 0`).

Счётчик тикает каждую секунду, поэтому виджет не ждёт stats (они приходят раз в
`WIDGET_UPDATE_INTERVAL`), а сам читает `get_countdown_remaining()` на секундном
тике менеджера. Из stats нужен только контекст дня: рабочий ли он и выработана
ли норма. Мигание идёт по отдельному тику `tick_blink()` (~500мс) — тому же,
что крутит мигание в заголовке, поэтому обе анимации в одной фазе.
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

# Начертания текста счётчика. BLINK — не начертание, а режим: реальный вес
# берётся из фазы мигания (см. _weight).
_NORMAL = "normal"
_BOLD = "bold"
_BLINK = "blink"


class CountdownWidget(BaseMiniWidget):
    """Круг с обратным отсчётом до неактивности."""

    caption = WIDGET_CAPTION_COUNTDOWN

    def __init__(self, *args, **kwargs):
        # Контекст дня из последних stats — обновляется раз в минуту,
        # а перерисовка идёт каждую секунду.
        self._is_working_day = True
        self._goal_reached = False
        # Фаза мигания в предупредительной фазе: True — текущий кадр жирный.
        self._blink_bold = False
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

    def tick_blink(self):
        """Шаг мигания (~500мс) — в такт с миганием заголовка."""
        text, color, mode = self._state()
        if mode != _BLINK:
            # Не в предупредительной фазе: гасим фазу, чтобы после возврата
            # в неё мигание начиналось с жирного кадра, как в заголовке.
            self._blink_bold = False
            return
        self._blink_bold = not self._blink_bold
        self._draw(text, color, self._weight(mode))

    def _refresh(self):
        text, color, mode = self._state()
        if mode != _BLINK:
            self._blink_bold = False
        self._draw(text, color, self._weight(mode))

    def _weight(self, mode: str) -> str:
        """Начертание кадра: для мигания — по текущей фазе."""
        if mode == _BLINK:
            return _BOLD if self._blink_bold else _NORMAL
        return mode

    def _state(self) -> tuple[str, str, str]:
        """(текст, цвет заливки, режим начертания) по состоянию счётчика."""
        if not self._is_working_day:
            return "—", theme.COLOR_GRAY, _NORMAL

        # Норма выработана и отсчёт остановлен настройкой — как в заголовке:
        # зелёный заполнитель вместо цифр.
        if self._goal_reached and config.STOP_COUNTDOWN_AT_RECOMMENDED:
            return _GOAL_PLACEHOLDER, theme.COLOR_GREEN, _NORMAL

        remaining = get_countdown_remaining()
        if remaining is None:
            return "—", theme.COLOR_GRAY, _NORMAL

        minutes, secs = divmod(remaining, 60)
        text = f"{minutes:02d}:{secs:02d}"

        if remaining == 0:
            # Пользователь уже неактивен — жирный красный без мигания.
            return text, theme.COLOR_RED, _BOLD

        warning = config.COUNTDOWN_WARNING_SECONDS
        if warning > 0 and remaining <= warning:
            return text, theme.COLOR_RED, _BLINK
        return text, theme.COLOR_GREEN, _NORMAL

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
