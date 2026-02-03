# user_active_time
Монитор логинов/разлогинов пользователя Windows
Работает без прав администратора

**Что отслеживается:**
- `LOGON` — вход в систему
- `LOGOFF` — выход из системы  
- `LOCK` — блокировка экрана (Win+L)
- `UNLOCK` — разблокировка экрана

**Как использовать:**

1. Сохрани как `session_monitor.py`
2. Запусти: `python session_monitor.py`
3. Лог пишется в `C:\Users\<твой_юзер>\session_log.txt`

**Автозапуск без админки:**

Добавь ярлык в автозагрузку пользователя:
```
Win+R → shell:startup → создай ярлык на pythonw.exe session_monitor.py