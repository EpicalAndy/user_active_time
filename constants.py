import ctypes
from ctypes import wintypes

# === Общие константы ===

ENCODING = "utf-8"
FONT_FAMILY = "Segoe UI"

# === Цвета UI ===

COLOR_DARK_BG = "#2C3E50"       # Основной тёмный фон (заголовок, окно отчёта)
COLOR_DARKER_BG = "#34495E"     # Вторичный тёмный фон (тулбар)
COLOR_LIGHT_FG = "#ECF0F1"      # Основной светлый текст
COLOR_WHITE = "#FFFFFF"         # Белый текст
COLOR_HOVER = "#5D6D7E"         # Состояние при наведении
COLOR_MUTED = "#95A5A6"         # Приглушённый текст / сетка
COLOR_LIGHT_GRAY = "#BDC3C7"    # Светло-серый фон
COLOR_GRAY = "#7F8C8D"          # Серый (нерабочий день)
COLOR_GREEN = "#27AE60"         # Успех / активность
COLOR_YELLOW = "#F39C12"        # Предупреждение
COLOR_RED = "#E74C3C"           # Опасность / простой
COLOR_BLUE = "#3498DB"          # Пользовательское (ручное) время
COLOR_TOOLTIP_BG = "#FFFFE1"    # Фон подсказки
COLOR_TOOLTIP_FG = "#333333"    # Текст подсказки

# === Подсказки кнопок Тулбара ===

TOOLTIP_ADD_ACTIVE_TIME = "Добавить активное время"
TOOLTIP_OPEN_SETTINGS = "Настройки"
DEFAULT_MANUAL_ACTIVITY_DESCRIPTION = "Добавлено пользовательское время"

# === Меню «Отчёты» ===

REPORTS_MENU_LABEL = "Отчёты"
REPORT_MENU_FOLDER = "Папка с отчётами"
REPORT_MENU_DAILY = "Дневной отчёт"
REPORT_MENU_PERIOD = "Отчёт за период"

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
PERIOD_DIALOG_ERROR_NO_DATA_TEMPLATE = (
    "Нет отчётов по граничным датам периода: {dates}.\n\n"
    "Выберите даты, для которых есть отчёты в папке."
)

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

# === Поля метрик в дневном TXT-отчёте ===
# Внутренние ключи (стабильные, в файл не меняются) и дефолтные русские метки.
# Метки записываются в секцию [Поля метрик] файла отчёта при его создании.
# Парсер периодного отчёта берёт метки оттуда; если секции нет — использует
# эти дефолты (что обеспечивает обратную совместимость со старыми файлами).

REPORT_FIELDS_SECTION_HEADER = "[Поля метрик]"

REPORT_KEY_ACTIVE_TIME = "active_time"
REPORT_KEY_TOTAL_WORK = "total_work"
REPORT_KEY_MAX_WORK = "max_work"

REPORT_FIELD_ACTIVE_TIME = "Общее активное время"
REPORT_FIELD_TOTAL_WORK = "Общее время работы"
REPORT_FIELD_MAX_WORK = "Максимальное рабочее время"

REPORT_DEFAULT_FIELD_LABELS: dict[str, str] = {
    REPORT_KEY_ACTIVE_TIME: REPORT_FIELD_ACTIVE_TIME,
    REPORT_KEY_TOTAL_WORK: REPORT_FIELD_TOTAL_WORK,
    REPORT_KEY_MAX_WORK: REPORT_FIELD_MAX_WORK,
}

# === Названия метрик ===
# *_FULL — расширенная форма для настроек; короткая — для тела виджета и отчёта.

METRIC_ACTIVE_TIME = "Активное время"
METRIC_SESSION_COUNT = "Сессий"
METRIC_SESSION_COUNT_FULL = "Количество сессий"
METRIC_ACTIVITY_PERCENT = "Активность"
METRIC_ACTIVITY_PERCENT_FULL = "Активность (%)"
METRIC_FULL_DAY_TIME = "Рабочее время"
METRIC_REMAINING_TIME_FULL = "Осталось до конца дня"
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
