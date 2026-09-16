"""
Windows API: константы сообщений и сессий, коды клавиш, типы и функции ctypes.

Всё, что нужно монитору сессий (WTS-уведомления через скрытое окно) и
низкоуровневым хукам ввода (WH_KEYBOARD_LL / WH_MOUSE_LL). Без прав
администратора — см. developer_guide, разделы «Мониторинг сессий» и
«Мониторинг ввода».
"""

import ctypes
from ctypes import wintypes

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

# Сообщения клавиатуры, приходящие в WH_KEYBOARD_LL.
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Виртуальные коды модификаторов. Обобщённые (VK_CONTROL и т.п.) в хук не
# приходят — там всегда конкретная сторона (VK_LCONTROL / VK_RCONTROL),
# поэтому обе стороны сводятся к одному имени модификатора (см. tools/input_lock/hotkey.py).
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12          # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

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


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """Полезная нагрузка WH_KEYBOARD_LL: lParam указывает на неё.

    Нужна только ради `vkCode` — какая именно клавиша нажата. Разыменование
    делается прямо в hook-колбэке, поэтому дальше vkCode обрабатывается
    сравнениями целых, без обращений к Windows API.
    """

    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


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
