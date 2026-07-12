import ctypes
from ctypes import wintypes

# === Общие константы ===

ENCODING = "utf-8"
FONT_FAMILY = "Segoe UI"

# === Цвета UI ===
#
# Цветовые параметры переехали в theme.py (палитры тёмной/светлой тем).
# Модули читают цвета динамически как `theme.COLOR_X` — см. theme.py.

# === Подсказки кнопок Тулбара ===

TOOLTIP_ADD_ACTIVE_TIME = "Добавить активное время"
TOOLTIP_OPEN_SETTINGS = "Настройки"
TOOLTIP_HELP = "Помощь"
DEFAULT_MANUAL_ACTIVITY_DESCRIPTION = "Добавлено пользовательское время"

# === Меню «Помощь» ===

HELP_MENU_LABEL = "❓"
HELP_MENU_README = "Помощь"
HELP_MENU_GITHUB = "github"
# «Помощь» открывает локальный README.md (поставляется со сборкой — см. main.spec).
GITHUB_URL = "https://github.com/EpicalAndy/user_active_time"

# === Меню «Отчёты» ===

REPORTS_MENU_LABEL = "Отчёты"
REPORT_MENU_TODAY = "Отчёт за сегодня"
REPORT_MENU_LAST = "Последний дневной отчёт"
REPORT_MENU_FOLDER = "Папка с отчётами"
REPORT_MENU_DAILY = "Дневной отчёт"
REPORT_MENU_HEATMAP = "Тепловая карта"
REPORT_MENU_PERIOD = "Отчёт за период"

# Ошибки для быстрых пунктов «сегодня» / «последний»
REPORT_NO_DATA_TITLE = "Нет отчёта"
REPORT_NO_TODAY_TEXT = (
    "Отчёт за сегодня ещё не создан. Активность за день должна быть записана,"
    " чтобы появился JSON-файл."
)
REPORT_NO_PAST_TEXT = "В папке отчётов не найдено ни одного прошлого дневного отчёта."

# === Окно тепловой карты ===

HEATMAP_WINDOW_TITLE = "Тепловая карта активности"
HEATMAP_LEGEND_HIGH = "≥ {threshold}% (норма)"
HEATMAP_LEGEND_MID = "{min}–{max}%"
HEATMAP_LEGEND_LOW = "< {threshold}%"
HEATMAP_LEGEND_NO_DATA = "Нет данных"
HEATMAP_CLOSE = "Закрыть"
HEATMAP_TOOLTIP_NO_DATA = "Нет данных"
HEATMAP_TOOLTIP_ACTIVE = "Активное"
HEATMAP_TOOLTIP_NORM = "Норма"
HEATMAP_TOOLTIP_PERCENT = "Активность"

# === Календарь рабочего времени (планировщик-исключения) ===

SCHEDULE_CALENDAR_TITLE = "Календарь рабочего времени"
SCHEDULE_CLOSE = "Закрыть"
SCHEDULE_LEGEND_OVERRIDE = "Свой лимит"
SCHEDULE_LEGEND_DAYOFF = "Выходной"
SCHEDULE_LEGEND_DEFAULT = "По расписанию"
SCHEDULE_LEGEND_NOTE = "• заметка"
SCHEDULE_TOOLTIP_LIMIT = "Лимит"
SCHEDULE_TOOLTIP_DAYOFF = "Выходной"
SCHEDULE_TOOLTIP_DEFAULT = "По расписанию (день недели)"
SCHEDULE_TOOLTIP_HOURS_UNIT = "ч"

# Диалог настройки одного дня
DAY_DIALOG_TITLE = "Настройка дня"
DAY_DIALOG_HOURS_LABEL = "Лимит часов:"
DAY_DIALOG_DAYOFF = "Выходной (не отслеживать)"
DAY_DIALOG_USE_SCHEDULE = "По расписанию"
DAY_DIALOG_NOTE_LABEL = "Заметка:"
DAY_DIALOG_SAVE = "Сохранить"
DAY_DIALOG_CANCEL = "Отмена"

# Кнопка вызова календаря из диалога настроек
SETTINGS_CALENDAR_BUTTON = "Календарь рабочего времени…"

# === Диалог «Отчёт за период» ===

PERIOD_DIALOG_TITLE = "Отчёт за период"
PERIOD_DIALOG_FROM_LABEL = "С:"
PERIOD_DIALOG_TO_LABEL = "По:"
PERIOD_DIALOG_DATE_PLACEHOLDER = "дд.мм.гггг"
PERIOD_DIALOG_BUILD_BUTTON = "Построить отчёт"
PERIOD_DIALOG_CALENDAR_BUTTON = "📅"
CALENDAR_POPUP_TITLE = "Календарь"
PERIOD_DIALOG_ERROR_INVALID = "Введите корректные даты в формате дд.мм.гггг"
PERIOD_DIALOG_ERROR_RANGE = "Дата «По» должна быть позже даты «С»"
PERIOD_DIALOG_ERROR_SAME_DAY = "Период должен охватывать больше одного дня"
PERIOD_DIALOG_ERROR_NO_DATA_TITLE = "Нет данных"
PERIOD_DIALOG_ERROR_NO_DATA_TEMPLATE = "В выбранном диапазоне нет ни одного отчёта."

# === Окно отчёта за период ===

PERIOD_REPORT_WINDOW_TITLE = "Отчёт за период"
PERIOD_REPORT_PERIOD_LABEL = "Период"
PERIOD_REPORT_TOTALS_LABEL = "Итого за период"
PERIOD_REPORT_BREAKDOWN_LABEL = "По дням"
PERIOD_REPORT_TOTAL_ACTIVE = "Общее активное время"
PERIOD_REPORT_TOTAL_WORK = "Общее время работы"
PERIOD_REPORT_TOTAL_MAX_WORK = "Максимальное рабочее время (норма)"
PERIOD_REPORT_DEFICIT_ACTIVE = "Недобор активности до рекомендуемой нормы"
PERIOD_REPORT_DEFICIT_WORK = "Недобор рабочего времени до нормы"
PERIOD_REPORT_COL_DATE = "Дата"
PERIOD_REPORT_COL_ACTIVE = "Активное"
PERIOD_REPORT_COL_WORK = "Работа"
PERIOD_REPORT_COL_MAX = "Норма"
PERIOD_REPORT_COL_ACTIVE_PCT = "Акт. %"
PERIOD_REPORT_COL_WORK_PCT = "Раб. %"
PERIOD_REPORT_CLOSE = "Закрыть"
PERIOD_REPORT_NO_NORM = "—"

# === Дневной JSON-отчёт ===
# Файлы отчётов: {username}_dd.mm.yyyy.json. Версия схемы повышается при
# несовместимых изменениях формата.
#
# v2: добавлены сырые интервалы `sessions` и `idle`; `active_seconds` стал
# вычисляемой проекцией от них и текущего таймаута неактивности.
REPORT_JSON_VERSION = 2
REPORT_JSON_EXT = ".json"

# Минимальная длина (сек) гэпа простоя ввода, который регистрируется в `idle`.
# Пересчёт активного времени точен для таймаута неактивности ≥ этого значения;
# значение заведомо меньше реалистичных таймаутов.
MIN_IDLE_GAP_SECONDS = 5

# === Названия метрик ===
# *_FULL — расширенная форма для настроек; короткая — для тела виджета и отчёта.

METRIC_ACTIVE_TIME = "Активное время"
METRIC_SESSION_COUNT = "Сессий"
METRIC_SESSION_COUNT_FULL = "Количество сессий"
METRIC_ACTIVITY_PERCENT = "Активность"
METRIC_ACTIVITY_PERCENT_FULL = "Активность (%)"
METRIC_FULL_DAY_TIME = "Рабочее время"
METRIC_FULL_DAY_TIME_PERCENT_FULL = "Рабочее время (%)"
METRIC_REMAINING_TIME_FULL = "Осталось до конца дня"
METRIC_REMAINING_TIME_PERCENT_FULL = "Осталось до конца дня (%)"
METRIC_RECOMMENDED_REMAINING_FULL = "До рекомендуемой нормы"
METRIC_RECOMMENDED_REMAINING_PERCENT_FULL = "До рекомендуемой нормы (%)"
METRIC_WORK_DAY_END_FULL = "Окончание рабочего дня"
METRIC_FIRST_LOGIN = "Начало рабочего дня"
METRIC_LAST_LOGOUT = "Конец рабочего дня"
METRIC_HIDE_OPTION = "Не отображать"

# === Константы Windows API ===

WM_WTSSESSION_CHANGE = 0x02B1
WM_QUIT = 0x0012
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5
WTS_SESSION_LOGOFF = 0x6
NOTIFY_FOR_THIS_SESSION = 0

# === Константы для низкоуровневых хуков ввода ===
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200

# === Типы, структуры и функции Windows API (ctypes) ===

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


# Тип callback для низкоуровневых хуков (SetWindowsHookExW)
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,       # LRESULT
    ctypes.c_int,        # nCode
    wintypes.WPARAM,     # wParam
    wintypes.LPARAM,     # lParam
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
wtsapi32 = ctypes.windll.wtsapi32

user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.RegisterClassW.restype = wintypes.ATOM
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.DefWindowProcW.restype = ctypes.c_long
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

# SetWindowsHookExW
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,        # idHook
    HOOKPROC,            # lpfn
    wintypes.HINSTANCE,  # hMod
    wintypes.DWORD,      # dwThreadId
]

# UnhookWindowsHookEx
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]

# CallNextHookEx
user32.CallNextHookEx.restype = ctypes.c_long
user32.CallNextHookEx.argtypes = [
    wintypes.HANDLE,     # hhk
    ctypes.c_int,        # nCode
    wintypes.WPARAM,     # wParam
    wintypes.LPARAM,     # lParam
]

# PostThreadMessageW
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,      # idThread
    wintypes.UINT,       # Msg
    wintypes.WPARAM,     # wParam
    wintypes.LPARAM,     # lParam
]
