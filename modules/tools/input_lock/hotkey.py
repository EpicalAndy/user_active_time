"""
Разбор и распознавание горячей комбинации для блокировки ввода.

Модуль намеренно не знает ни про хуки, ни про Windows API: на вход приходят
уже разобранные (vk, нажата/отпущена), на выходе — факт срабатывания. Такое
разделение даёт две вещи: логику можно покрыть тестами без окон и хуков,
а в hook-колбэке остаются только сравнения целых.

Почему состояние модификаторов ведётся вручную, а не читается у Windows:
пока ввод заблокирован, нажатия проглатываются нашим же фильтром, и обычные
механизмы (RegisterHotKey, состояние клавиатуры очереди) их уже не видят —
LL-хук стоит в цепочке раньше. Значит, единственный, кто знает о зажатом
Ctrl во время блокировки, — это мы сами.
"""

from constants import (
    VK_CONTROL,
    VK_LCONTROL,
    VK_LMENU,
    VK_LSHIFT,
    VK_LWIN,
    VK_MENU,
    VK_RCONTROL,
    VK_RMENU,
    VK_RSHIFT,
    VK_RWIN,
    VK_SHIFT,
)

# Имя модификатора → все vk-коды, которые его дают (обе стороны клавиатуры).
_MODIFIER_VKS = {
    "ctrl": (VK_CONTROL, VK_LCONTROL, VK_RCONTROL),
    "alt": (VK_MENU, VK_LMENU, VK_RMENU),
    "shift": (VK_SHIFT, VK_LSHIFT, VK_RSHIFT),
    "win": (VK_LWIN, VK_RWIN),
}

# Обратная карта vk → имя модификатора (строится один раз при импорте).
_VK_TO_MODIFIER = {
    vk: name for name, vks in _MODIFIER_VKS.items() for vk in vks
}

# Отображаемые названия модификаторов в подписи комбинации.
_MODIFIER_LABELS = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}

# Порядок модификаторов в подписи — привычный по Windows.
_MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")

# Обычные клавиши, у которых имя не совпадает с символом.
_NAMED_KEYS = {
    "space": 0x20,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "enter": 0x0D,
    "backspace": 0x08,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pause": 0x13,
    "scrolllock": 0x91,
}

_NAMED_KEY_LABELS = {vk: name.capitalize() for name, vk in _NAMED_KEYS.items()}


class Hotkey:
    """Разобранная комбинация: набор модификаторов + одна обычная клавиша."""

    def __init__(self, modifiers: frozenset, vk: int, label: str):
        self.modifiers = modifiers
        self.vk = vk
        self.label = label

    def __repr__(self):
        return f"Hotkey({self.label!r})"


def _key_vk(token: str) -> int | None:
    """vk-код обычной (не модификатора) клавиши по её имени."""
    if token in _NAMED_KEYS:
        return _NAMED_KEYS[token]
    if len(token) == 1 and (token.isalpha() or token.isdigit()):
        return ord(token.upper())
    if token.startswith("f") and token[1:].isdigit():
        number = int(token[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1  # VK_F1 = 0x70
    return None


def _key_label(vk: int) -> str:
    if vk in _NAMED_KEY_LABELS:
        return _NAMED_KEY_LABELS[vk]
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x70 + 1}"
    return chr(vk)


def parse_hotkey(text: str) -> Hotkey | None:
    """Разбирает строку вида "ctrl+alt+shift+U". None, если строка негодная.

    Требуется хотя бы один модификатор: комбинация без него отобрала бы у
    пользователя обычную клавишу во всех приложениях сразу.
    """
    if not text:
        return None

    modifiers = set()
    key_vk = None
    for raw in text.split("+"):
        token = raw.strip().lower()
        if not token:
            return None
        if token in ("control",):
            token = "ctrl"
        if token in _MODIFIER_VKS:
            modifiers.add(token)
            continue
        if key_vk is not None:
            return None  # две обычные клавиши в одной комбинации
        key_vk = _key_vk(token)
        if key_vk is None:
            return None

    if key_vk is None or not modifiers:
        return None

    parts = [_MODIFIER_LABELS[name] for name in _MODIFIER_ORDER if name in modifiers]
    parts.append(_key_label(key_vk))
    return Hotkey(frozenset(modifiers), key_vk, "+".join(parts))


class HotkeyMatcher:
    """Отслеживает зажатые модификаторы и ловит момент срабатывания комбинации.

    `feed` возвращает True ровно один раз на нажатие: авторепит зажатой
    клавиши не даёт повторных срабатываний.
    """

    def __init__(self, hotkey: Hotkey | None = None):
        self._hotkey = hotkey
        self._pressed_modifiers: set = set()
        self._triggered = False

    def set_hotkey(self, hotkey: Hotkey | None):
        self._hotkey = hotkey
        self.reset()

    @property
    def hotkey(self) -> Hotkey | None:
        return self._hotkey

    def reset(self):
        """Сбрасывает состояние зажатых клавиш.

        Нужен там, где отпускание клавиши до нас не доходит: экран блокировки
        и другие защищённые рабочие столы наши хуки не видят, поэтому после
        возврата модификатор считался бы зажатым вечно.
        """
        self._pressed_modifiers.clear()
        self._triggered = False

    def feed(self, vk: int, is_down: bool) -> bool:
        """Скармливает событие клавиши. True — комбинация сработала сейчас."""
        modifier = _VK_TO_MODIFIER.get(vk)
        if modifier is not None:
            if is_down:
                self._pressed_modifiers.add(modifier)
            else:
                self._pressed_modifiers.discard(modifier)
                self._triggered = False
            return False

        if self._hotkey is None or vk != self._hotkey.vk:
            return False

        if not is_down:
            self._triggered = False
            return False

        if self._triggered:
            return False  # авторепит
        if self._pressed_modifiers != set(self._hotkey.modifiers):
            return False

        self._triggered = True
        return True

    def is_hotkey_key(self, vk: int) -> bool:
        """Участвует ли клавиша в комбинации (модификатор или основная)."""
        if vk in _VK_TO_MODIFIER:
            return True
        return self._hotkey is not None and vk == self._hotkey.vk
