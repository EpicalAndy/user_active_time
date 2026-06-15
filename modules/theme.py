"""
Темы оформления интерфейса (тёмная / светлая).

Сюда вынесены ВСЕ цветовые параметры UI. Раньше они жили в constants.py,
теперь палитры собраны здесь, а конкретный набор цветов выбирается темой.

Конвенция чтения (важно!): модули должны читать цвета динамически как
`theme.COLOR_X` (через `import theme`), а НЕ через `from theme import COLOR_X`.
`from ... import` биндит значение на момент импорта модуля, и смена темы
до перезапуска не применится — та же ловушка, что описана в config.py.
Динамическое чтение `theme.COLOR_X` — единственное, что нужно, чтобы окна,
открытые после переключения темы, отрисовались в новой палитре.

Постоянный виджет уже созданными tk-виджетами сам не перекрашивается,
поэтому после смены темы он пересобирает свою «хромированную» часть —
см. ActivityWidget._apply_theme.

Активная тема инициализируется из config.THEME при импорте модуля
и переключается через set_theme() (диалог настроек).
"""

import config

# Идентификаторы тем (значения config.THEME).
THEME_DARK = "dark"
THEME_LIGHT = "light"

# Человекочитаемые названия для диалога настроек.
THEME_LABELS = {
    THEME_DARK: "Тёмная",
    THEME_LIGHT: "Светлая",
}

# Палитры. Имена ролей сохранены историческими (COLOR_DARK_BG и т.п.) —
# это «роли», а не буквальные цвета: в светлой теме COLOR_DARK_BG держит
# светлый фон. Каждая палитра определяет один и тот же набор ролей.
_PALETTES: dict[str, dict[str, str]] = {
    THEME_DARK: {
        "COLOR_DARK_BG": "#2C3E50",     # Основной фон (заголовок, окно отчёта)
        "COLOR_DARKER_BG": "#34495E",   # Вторичный фон (тулбар)
        "COLOR_LIGHT_FG": "#ECF0F1",    # Основной текст
        "COLOR_WHITE": "#FFFFFF",       # Текст на цветной заливке (статус-фон)
        "COLOR_HOVER": "#5D6D7E",       # Состояние при наведении
        "COLOR_MUTED": "#95A5A6",       # Приглушённый текст / сетка / разделители
        "COLOR_LIGHT_GRAY": "#BDC3C7",  # Мягкая поверхность / трек графика
        "COLOR_GRAY": "#7F8C8D",        # Нейтральный (нерабочий день / нет данных)
        "COLOR_GREEN": "#27AE60",       # Успех / активность
        "COLOR_YELLOW": "#F39C12",      # Предупреждение
        "COLOR_RED": "#E74C3C",         # Опасность / простой
        "COLOR_BLUE": "#3498DB",        # Пользовательское (ручное) время
        "COLOR_TOOLTIP_BG": "#FFFFE1",  # Фон подсказки
        "COLOR_TOOLTIP_FG": "#333333",  # Текст подсказки
    },
    THEME_LIGHT: {
        "COLOR_DARK_BG": "#ECEFF1",     # Основной светлый фон
        "COLOR_DARKER_BG": "#CFD8DC",   # Вторичный фон (тулбар)
        "COLOR_LIGHT_FG": "#263238",    # Основной тёмный текст
        "COLOR_WHITE": "#FFFFFF",       # Текст на цветной заливке (статус-фон)
        "COLOR_HOVER": "#B0BEC5",       # Состояние при наведении
        "COLOR_MUTED": "#78909C",       # Приглушённый текст / сетка / разделители
        "COLOR_LIGHT_GRAY": "#CFD8DC",  # Мягкая поверхность / трек графика
        "COLOR_GRAY": "#90A4AE",        # Нейтральный (нерабочий день / нет данных)
        "COLOR_GREEN": "#2E7D32",       # Успех / активность
        "COLOR_YELLOW": "#EF6C00",      # Предупреждение
        "COLOR_RED": "#C62828",         # Опасность / простой
        "COLOR_BLUE": "#1565C0",        # Пользовательское (ручное) время
        "COLOR_TOOLTIP_BG": "#FFFDE7",  # Фон подсказки
        "COLOR_TOOLTIP_FG": "#333333",  # Текст подсказки
    },
}

# Подписчики на смену темы (например, постоянный виджет регистрирует
# свою перекраску). Вызываются после применения новой палитры.
_listeners: list = []

_current_theme = THEME_DARK


def available_themes() -> list[str]:
    """Список доступных идентификаторов тем (для UI настроек)."""
    return [THEME_DARK, THEME_LIGHT]


def current_theme() -> str:
    """Идентификатор активной темы."""
    return _current_theme


def _apply_palette(name: str) -> None:
    """Публикует цвета палитры как атрибуты модуля (theme.COLOR_X)."""
    globals().update(_PALETTES[name])


def set_theme(name: str, *, notify: bool = True) -> None:
    """Переключает активную тему и перепривязывает theme.COLOR_*.

    notify=True — уведомляет подписчиков (для live-перекраски уже открытых
    долгоживущих окон вроде виджета). Окна, создаваемые после вызова,
    подхватят новую палитру сами через динамическое чтение theme.COLOR_X.
    """
    global _current_theme
    if name not in _PALETTES:
        name = THEME_DARK
    _current_theme = name
    _apply_palette(name)
    if notify:
        for callback in list(_listeners):
            callback()


def subscribe(callback) -> None:
    """Регистрирует callback, вызываемый после каждой смены темы."""
    _listeners.append(callback)


def unsubscribe(callback) -> None:
    """Снимает регистрацию callback'а смены темы."""
    if callback in _listeners:
        _listeners.remove(callback)


# Инициализация при импорте: берём тему из config, иначе тёмную.
_initial = getattr(config, "THEME", THEME_DARK)
set_theme(_initial if _initial in _PALETTES else THEME_DARK, notify=False)
