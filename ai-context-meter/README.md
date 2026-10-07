# AI Context Meter (Windows)

Маленькое окно поверх всех окон с полосками заполнения контекста.

## Быстрый запуск
Двойной клик по `start.bat` — сам доустановит `pywinauto` и откроет окно (нужен только Python). `add_autostart.bat` — добавить запуск при входе в Windows.

## Запуск вручную
1. Python 3.9+ (с tkinter) и `pip install pywinauto`.
2. `pythonw meter.py` (без консоли) или `python meter.py`.
3. Перетаскивание — ЛКМ, выход — ПКМ → Exit. Настройки: `%USERPROFILE%\.ai_context_meter.json`.
4. Автозапуск: ярлык на `pythonw.exe meter.py` в `shell:startup`.

## Источники
- **Claude Code** — точно: токены последнего ответа из `%USERPROFILE%\.claude\projects\*\*.jsonl`. Для 1M-контекста: `claude_code_window: 1000000`.
- **Десктоп-клиенты (Claude, ChatGPT)** — оценка: утилита читает текст из окна приложения через Windows UI Automation и делит число символов на 3,5. Список приложений (`apps`: имя, exe, окно в токенах) правится в конфиге.

Ограничения: у клиентов нет API размера контекста; Electron-приложения могут отдавать в UI Automation не весь текст (длинный чат виртуализируется), тогда процент занижен. Имя exe проверьте в Диспетчере задач.
