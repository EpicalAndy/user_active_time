"""
Обратный отсчёт до неактивности в заголовке виджета и индикация вокруг него.

Отвечает за три связанные вещи, которые нельзя разнести — они переключают
одни и те же состояния:

- countdown-лейбл: «MM:SS», в предупредительной фазе мигает (жирный красный
  ↔ обычный), на нуле — сплошной жирный красный;
- лейбл названия «Активность» в заголовке — мигает в такт countdown'у, а в
  режиме «норма выработана» принудительно зелёный;
- цвет рамки окна (`border_color`) — приоритеты между прогрессом по
  активности (зелёный/жёлтый) и алертами countdown'а (красный).

Сам лейбл названия создаёт `TitleBar` и передаёт сюда; countdown-лейбл и
слот под него создаются здесь, внутри фрейма заголовка. Слот фиксированной
ширины по жирному «88:88»: мигающий текст растёт симметрично и не толкает
метрики справа.

Включён ли мониторинг ввода (`input_monitoring_enabled`) читается один раз
при создании: появление/исчезание countdown'а требует перезапуска (`enabled`).
"""

import tkinter as tk

import config
from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from modules import theme
from modules.ui_utils import bold_pixel_width
from utility import input_monitoring_enabled

# Состояния countdown'а для внешней индикации (рамка виджета).
_COUNTDOWN_NORMAL = "normal"
_COUNTDOWN_WARNING = "warning"
_COUNTDOWN_ZERO = "zero"

# Уровни прогресса по активности — задают цвет рамки виджета.
# Шкала та же, что у метрик в теле виджета (см. body._color_for_percent):
# норма → зелёный, минимум → жёлтый, ниже минимума → без индикации.
PROGRESS_NONE = "none"
PROGRESS_MIN = "min"
PROGRESS_GOAL = "goal"

_PLACEHOLDER = "__:__"


class CountdownIndicator:
    """Countdown в заголовке + мигание названия + цвет рамки."""

    def __init__(self, frame: tk.Frame, title_label: tk.Label):
        self._title_label = title_label

        self._blinking = False
        self._blink_bold = False
        self._state = _COUNTDOWN_NORMAL
        # Режим «норма выработана»: название и рамка всегда зелёные.
        # _goal_placeholder=True дополнительно заменяет countdown на «__:__».
        self._goal_reached = False
        self._goal_placeholder = False
        # Уровень прогресса для рамки. Живёт отдельно от _goal_reached:
        # тот завязан на countdown (и без него не выставляется), а рамка
        # должна подсвечиваться независимо от таймера неактивности.
        self._progress_level = PROGRESS_NONE

        self._slot: tk.Frame | None = None
        self._label: tk.Label | None = None
        if input_monitoring_enabled():
            width = max(
                bold_pixel_width("88:88", MAIN_FONT_SIZE - 1),
                bold_pixel_width(_PLACEHOLDER, MAIN_FONT_SIZE - 1),
            ) + 4
            self._slot = tk.Frame(frame, bg=theme.COLOR_DARK_BG, width=width)
            self._slot.pack(side=tk.LEFT, fill=tk.Y)
            self._slot.pack_propagate(False)
            self._label = tk.Label(
                self._slot, text="",
                bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            self._label.pack(expand=True)

    @property
    def enabled(self) -> bool:
        return self._label is not None

    def drag_widgets(self) -> list[tk.Widget]:
        """Свои виджеты, за которые тоже тянется окно."""
        return [w for w in (self._slot, self._label) if w is not None]

    # --- Countdown ---

    def update(self, remaining: int | None):
        """Применяет остаток до неактивности к countdown-лейблу.

        remaining: None — сессии нет / не отслеживается, скрываем текст.
        0 — пользователь неактивен, жирный красный без мигания.
        >0 — таймер обратного отсчёта; вблизи нуля включается мигание.

        В режиме «норма выработана» (`_goal_reached`):
          * `_goal_placeholder=True` — обновление полностью пропускается
            (на месте countdown остаётся зелёный «__:__»);
          * иначе обновляются только цифры countdown, а цвет/шрифт
            названия не трогаются — оно остаётся зелёным.
        """
        if self._label is None:
            return
        if self._goal_placeholder:
            # Заполнитель уже отрисован в enter_goal_reached, не трогаем.
            return
        if remaining is None:
            self._label.configure(text="")
            self._blink_bold = False
            self._state = _COUNTDOWN_NORMAL
            return

        minutes, secs = divmod(remaining, 60)
        text = f"{minutes:02d}:{secs:02d}"

        if remaining == 0:
            # Неактивен — жирный красный, мигание выключено.
            self._state = _COUNTDOWN_ZERO
            self._blinking = False
            self._blink_bold = False
            self._label.configure(
                text=text, fg=theme.COLOR_RED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
            )
            self._apply_title_state(theme.COLOR_RED, weight="bold")
            return

        warning_threshold = config.COUNTDOWN_WARNING_SECONDS
        if warning_threshold > 0 and remaining <= warning_threshold:
            # Приближение к неактивности — мигание управляется тикером.
            self._state = _COUNTDOWN_WARNING
            self._label.configure(text=text, fg=theme.COLOR_LIGHT_FG)
            self._apply_title_state(theme.COLOR_LIGHT_FG, weight="normal")
            self._blinking = True
            return

        # Обычное состояние.
        self._state = _COUNTDOWN_NORMAL
        self._blinking = False
        self._blink_bold = False
        self._label.configure(
            text=text, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        )
        self._apply_title_state(theme.COLOR_LIGHT_FG, weight="normal")

    def _apply_title_state(self, color: str, weight: str):
        """Красит название «Активность» с учётом overriding'а goal_reached.

        Когда `_goal_reached` — название принудительно зелёное обычное.
        """
        if self._goal_reached:
            self._title_label.configure(
                fg=theme.COLOR_GREEN, font=(FONT_FAMILY, MAIN_FONT_SIZE),
            )
        else:
            self._title_label.configure(
                fg=color, font=(FONT_FAMILY, MAIN_FONT_SIZE, weight),
            )

    def clear(self):
        """Скрывает countdown (например, на нерабочем дне)."""
        if self._label is None:
            return
        self._label.configure(text="")
        self._blinking = False
        self._state = _COUNTDOWN_NORMAL
        # Сброс goal-состояния — на нерабочем дне нет смысла его держать.
        self.exit_goal_reached()

    def tick_blink(self):
        """Один шаг анимации мигания (вызывать каждые ~500мс)."""
        if not self._blinking or self._label is None:
            return
        self._blink_bold = not self._blink_bold
        weight = "bold" if self._blink_bold else "normal"
        fg = theme.COLOR_RED if self._blink_bold else theme.COLOR_LIGHT_FG
        self._label.configure(font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, weight), fg=fg)
        # Название мигает только если не в режиме «норма выработана».
        if not self._goal_reached:
            self._title_label.configure(font=(FONT_FAMILY, MAIN_FONT_SIZE, weight), fg=fg)

    # --- Режим «норма выработана» ---

    def enter_goal_reached(self, show_placeholder: bool):
        """Включает режим «норма выработана».

        Название «Активность» и countdown-alert (рамка) становятся
        зелёными — это работает всегда, пока режим активен.

        show_placeholder=True — countdown-лейбл заменяется зелёным
        «__:__», и update игнорируется до выхода из режима.
        show_placeholder=False — countdown продолжает обновляться
        и мигать по обычным правилам; зелёным остаётся только название.
        """
        if self._label is None:
            return
        self._goal_reached = True
        # Название сразу красим зелёным; следующий update учтёт флаг.
        self._title_label.configure(
            fg=theme.COLOR_GREEN, font=(FONT_FAMILY, MAIN_FONT_SIZE),
        )
        if show_placeholder:
            self._goal_placeholder = True
            self._state = _COUNTDOWN_NORMAL
            self._blinking = False
            self._blink_bold = False
            self._label.configure(
                text=_PLACEHOLDER, fg=theme.COLOR_GREEN,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
        else:
            self._goal_placeholder = False

    def exit_goal_reached(self):
        """Выключает режим «норма выработана» — возвращаемся к обычной логике."""
        self._goal_reached = False
        self._goal_placeholder = False

    # --- Рамка ---

    def set_progress_level(self, level: str):
        """Задаёт уровень прогресса по активности (PROGRESS_*) для рамки."""
        self._progress_level = level

    def border_color(self) -> str | None:
        """Цвет рамки окна виджета.

        Приоритеты:
        - Норма выработана → сплошной зелёный (перекрывает red-предупреждения:
          норма уже заработана, простой больше не важен).
        - Фаза нуля → сплошной красный (как у текста названия).
        - Фаза предупреждения, кадр «жирный красный» → красный.
        - Минимум взят (но норма ещё нет) → жёлтый. Стоит НИЖЕ красного:
          работа ещё не закончена, и предупреждение о простое важнее, чем
          индикация прогресса.
        - Иначе → None (индикатор не нужен).

        Обе подсветки прогресса (зелёная и жёлтая) выключаются настройкой
        WIDGET_PROGRESS_HIGHLIGHT — тогда рамка живёт только по правилам
        countdown'а, а зелёным при норме остаётся только название.
        """
        highlight = config.WIDGET_PROGRESS_HIGHLIGHT
        if highlight and self._progress_level == PROGRESS_GOAL:
            return theme.COLOR_GREEN
        if self._state == _COUNTDOWN_ZERO:
            return theme.COLOR_RED
        if self._state == _COUNTDOWN_WARNING and self._blink_bold:
            return theme.COLOR_RED
        if highlight and self._progress_level == PROGRESS_MIN:
            return theme.COLOR_YELLOW
        return None
