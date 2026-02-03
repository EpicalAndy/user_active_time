"""
Монитор логинов/разлогинов пользователя Windows
Работает без прав администратора
"""

import ctypes
import datetime
import json
import os
from ctypes import wintypes

# Папка для логов
LOG_DIR = os.path.join(os.path.expanduser("~"), "active_time")
os.makedirs(LOG_DIR, exist_ok=True)

# Файлы
LOG_FILE = os.path.join(LOG_DIR, "session_log.txt")
STATS_FILE = os.path.join(LOG_DIR, "daily_stats.json")

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


# === Отслеживание активного времени ===
session_start_time = None  # Когда началась текущая активная сессия


def load_stats() -> dict:
    """Загружает статистику из файла"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_stats(stats: dict):
    """Сохраняет статистику в файл"""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def format_duration(seconds: int) -> str:
    """Форматирует секунды в читаемый вид"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}ч {minutes}м {secs}с"


def start_session():
    """Начинает отсчёт активной сессии"""
    global session_start_time
    session_start_time = datetime.datetime.now()
    print(f"[SESSION] Сессия началась: {session_start_time.strftime('%H:%M:%S')}")


def end_session():
    """Завершает сессию и записывает время"""
    global session_start_time
    
    if session_start_time is None:
        print("[SESSION] Сессия не была начата, пропускаем")
        return
    
    end_time = datetime.datetime.now()
    
    # Если сессия перешла через полночь — разбиваем по дням
    current = session_start_time
    stats = load_stats()
    
    while current.date() < end_time.date():
        # Считаем время до конца дня
        midnight = datetime.datetime.combine(current.date() + datetime.timedelta(days=1), datetime.time.min)
        duration = (midnight - current).total_seconds()
        
        date_key = current.strftime("%Y-%m-%d")
        stats[date_key] = stats.get(date_key, 0) + int(duration)
        print(f"[STATS] {date_key}: +{format_duration(int(duration))}")
        
        current = midnight
    
    # Остаток в последний день
    duration = (end_time - current).total_seconds()
    date_key = end_time.strftime("%Y-%m-%d")
    stats[date_key] = stats.get(date_key, 0) + int(duration)
    print(f"[STATS] {date_key}: +{format_duration(int(duration))} (всего: {format_duration(stats[date_key])})")
    
    save_stats(stats)
    session_start_time = None


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
        
        # Управление сессией
        if wparam in (WTS_SESSION_UNLOCK, WTS_SESSION_LOGON):
            start_session()
        elif wparam in (WTS_SESSION_LOCK, WTS_SESSION_LOGOFF):
            end_session()
    
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


wnd_proc_callback = WNDPROC(wnd_proc)


def create_hidden_window():
    """Создаёт скрытое окно для получения системных сообщений"""
    hInstance = kernel32.GetModuleHandleW(None)
    class_name = "SessionMonitor_" + str(os.getpid())
    
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
        raise ctypes.WinError(ctypes.get_last_error())
    
    hwnd = user32.CreateWindowExW(
        0, class_name, "Session Monitor", 0,
        0, 0, 0, 0, None, None, hInstance, None
    )
    
    if not hwnd:
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
        raise RuntimeError("CreateWindowExW вернул NULL")
    
    return hwnd


def print_today_stats():
    """Показывает статистику за сегодня"""
    stats = load_stats()
    today = datetime.date.today().strftime("%Y-%m-%d")
    seconds = stats.get(today, 0)
    print(f"Активное время сегодня: {format_duration(seconds)}")


def main():
    print("=== Монитор сессий Windows ===")
    print(f"Папка логов: {LOG_DIR}")
    print(f"  - События: session_log.txt")
    print(f"  - Статистика: daily_stats.json")
    print()
    print_today_stats()
    print()
    print("Нажмите Ctrl+C для выхода\n")
    
    log_event("MONITOR_START (запуск мониторинга)")
    start_session()  # Считаем, что при запуске мониторинга пользователь активен
    
    hwnd = None
    try:
        hwnd = create_hidden_window()
        
        NOTIFY_FOR_THIS_SESSION = 0
        result = wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)
        if result:
            print("Подписка на события сессии: ОК")
        else:
            print("Предупреждение: не удалось подписаться на события")
        
        print("Мониторинг запущен. Для теста: Win+L\n")
        
        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        end_session()  # Сохраняем время при выходе
        log_event("MONITOR_STOP (остановка мониторинга)")
        if hwnd:
            wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            user32.DestroyWindow(hwnd)


if __name__ == "__main__":
    main()
