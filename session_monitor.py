"""
Монитор логинов/разлогинов пользователя Windows
Работает без прав администратора
"""

import ctypes
import datetime
import os
from ctypes import wintypes

# Путь к лог-файлу
LOG_FILE = os.path.join(os.path.expanduser("~"), "session_log.txt")

# Константы Windows
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5
WTS_SESSION_LOGOFF = 0x6

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
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

# Настраиваем типы возвращаемых значений — ЭТО ВАЖНО!
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,    # dwExStyle
    wintypes.LPCWSTR,  # lpClassName
    wintypes.LPCWSTR,  # lpWindowName
    wintypes.DWORD,    # dwStyle
    ctypes.c_int,      # x
    ctypes.c_int,      # y
    ctypes.c_int,      # nWidth
    ctypes.c_int,      # nHeight
    wintypes.HWND,     # hWndParent
    wintypes.HMENU,    # hMenu
    wintypes.HINSTANCE,# hInstance
    wintypes.LPVOID,   # lpParam
]

user32.RegisterClassW.restype = wintypes.ATOM
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]

user32.DefWindowProcW.restype = ctypes.c_long
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

user32.GetMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]

kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


def log_event(event_type: str):
    """Записывает событие в лог-файл"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = os.getenv("USERNAME", "unknown")
    line = f"{timestamp} | {username} | {event_type}\n"
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    
    print(f"[LOG] {line.strip()}")


def wnd_proc(hwnd, msg, wparam, lparam):
    """Обработчик сообщений окна"""
    if msg == WM_WTSSESSION_CHANGE:
        events = {
            WTS_SESSION_LOCK: "LOCK (блокировка)",
            WTS_SESSION_UNLOCK: "UNLOCK (разблокировка)", 
            WTS_SESSION_LOGON: "LOGON (вход)",
            WTS_SESSION_LOGOFF: "LOGOFF (выход)",
        }
        event_name = events.get(wparam, f"UNKNOWN ({wparam})")
        log_event(event_name)
    
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# Callback должен жить всё время работы программы
wnd_proc_callback = WNDPROC(wnd_proc)


def create_hidden_window():
    """Создаёт скрытое окно для получения системных сообщений"""
    hInstance = kernel32.GetModuleHandleW(None)
    
    class_name = "SessionMonitor_" + str(os.getpid())  # Уникальное имя
    
    wnd_class = WNDCLASSW()
    wnd_class.style = 0
    wnd_class.lpfnWndProc = wnd_proc_callback
    wnd_class.cbClsExtra = 0
    wnd_class.cbWndExtra = 0
    wnd_class.hInstance = hInstance
    wnd_class.hIcon = None
    wnd_class.hCursor = None
    wnd_class.hbrBackground = None
    wnd_class.lpszMenuName = None
    wnd_class.lpszClassName = class_name
    
    class_atom = user32.RegisterClassW(ctypes.byref(wnd_class))
    if not class_atom:
        error = ctypes.get_last_error()
        raise ctypes.WinError(error)
    
    hwnd = user32.CreateWindowExW(
        0,                      # dwExStyle
        class_name,             # lpClassName (используем строку, не atom)
        "Session Monitor",      # lpWindowName
        0,                      # dwStyle
        0, 0, 0, 0,            # x, y, width, height
        None,                   # hWndParent
        None,                   # hMenu
        hInstance,              # hInstance
        None                    # lpParam
    )
    
    if not hwnd:
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
        raise RuntimeError("CreateWindowExW вернул NULL без кода ошибки")
    
    return hwnd


def main():
    print("=== Монитор сессий Windows ===")
    print(f"Лог-файл: {LOG_FILE}")
    print("Нажмите Ctrl+C для выхода\n")
    
    log_event("MONITOR_START (запуск мониторинга)")
    
    hwnd = None
    try:
        hwnd = create_hidden_window()
        print(f"Окно создано: {hwnd}")
        
        # Регистрируемся на уведомления
        NOTIFY_FOR_THIS_SESSION = 0
        result = wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)
        if result:
            print("Подписка на события сессии: ОК")
        else:
            print("Предупреждение: не удалось подписаться на события")
        
        print("Мониторинг запущен. Заблокируй/разблокируй экран для теста (Win+L)")
        
        # Цикл обработки сообщений
        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:  # WM_QUIT
                break
            if ret == -1:  # Ошибка
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            
    except KeyboardInterrupt:
        print("\nОстановка по Ctrl+C...")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        log_event("MONITOR_STOP (остановка мониторинга)")
        if hwnd:
            wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            user32.DestroyWindow(hwnd)


if __name__ == "__main__":
    main()
