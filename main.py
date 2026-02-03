"""
Монитор логинов/разлогинов пользователя Windows
Работает без прав администратора
"""

import ctypes
import datetime
import os
import sys
import time
from ctypes import wintypes

# Путь к лог-файлу (в папке пользователя)
LOG_FILE = os.path.join(os.path.expanduser("~"), "session_log.txt")

# Константы Windows
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5
WTS_SESSION_LOGOFF = 0x6

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, 
                              wintypes.WPARAM, wintypes.LPARAM)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
wtsapi32 = ctypes.windll.wtsapi32

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

def create_hidden_window():
    """Создаёт скрытое окно для получения системных сообщений"""
    wnd_class = wintypes.WNDCLASSW()
    wnd_class.lpfnWndProc = WNDPROC(wnd_proc)
    wnd_class.hInstance = kernel32.GetModuleHandleW(None)
    wnd_class.lpszClassName = "SessionMonitor"
    
    class_atom = user32.RegisterClassW(ctypes.byref(wnd_class))
    if not class_atom:
        raise ctypes.WinError(ctypes.get_last_error())
    
    hwnd = user32.CreateWindowExW(
        0, class_atom, "Session Monitor",
        0, 0, 0, 0, 0,
        None, None, wnd_class.hInstance, None
    )
    
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())
    
    return hwnd

def main():
    print(f"=== Монитор сессий Windows ===")
    print(f"Лог-файл: {LOG_FILE}")
    print(f"Нажмите Ctrl+C для выхода\n")
    
    log_event("MONITOR_START (запуск мониторинга)")
    
    try:
        hwnd = create_hidden_window()
        
        # Регистрируемся на получение уведомлений о сессии
        NOTIFY_FOR_THIS_SESSION = 0
        if not wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION):
            print("Предупреждение: не удалось зарегистрироваться на уведомления")
        
        # Цикл обработки сообщений
        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        log_event("MONITOR_STOP (остановка мониторинга)")
        if 'hwnd' in locals():
            wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            user32.DestroyWindow(hwnd)

if __name__ == "__main__":
    main()

