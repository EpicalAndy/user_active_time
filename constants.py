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
TOOLTIP_OPEN_REPORTS = "Открыть папку с отчётами"
TOOLTIP_VIEW_REPORT = "Визуализация отчёта"
TOOLTIP_OPEN_SETTINGS = "Настройки"
DEFAULT_MANUAL_ACTIVITY_DESCRIPTION = "Добавлено пользовательское время"

# === Названия метрик ===
# *_FULL — расширенная форма для настроек; короткая — для тела виджета и отчёта.

METRIC_ACTIVE_TIME = "Активное время"
METRIC_SESSION_COUNT = "Сессий"
METRIC_SESSION_COUNT_FULL = "Количество сессий"
METRIC_ACTIVITY_PERCENT = "Активность"
METRIC_ACTIVITY_PERCENT_FULL = "Активность (%)"
METRIC_FULL_DAY_TIME = "Рабочее время"
METRIC_REMAINING_TIME = "Осталось рабочего время"
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
