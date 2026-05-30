# 📋 TegamCAL — Project Handoff Brief
**Обновлён: 2026-05-30**

## О проекте
Программа на Python для автоматизации калибровки **омметра Tegam 1750**.
Stage 1 — прототип для демо руководству.

## Где живёт проект
- Папка: `C:\Users\Govinda\Documents\TegamCAL`
- GitHub: `github.com/Elisei108/Tegam-Autocal`
- IDE: VS Code + Claude Desktop (Pro)

## Стек
- Python 3.14 + customtkinter (тёмная тема, 1280×800)
- pyserial — связь с приборами
- openpyxl — config.xlsx + будущие отчёты
- Arduino Nano Every (COM4, 9600) — 4 реле, ВСЕГДА реальный
- Tegam 1750 (COM3, 9600) — реальный или mock (USE_MOCK в config/)

## Что работает (✅)
- **Arduino + 4 реле** — щёлкают во всех режимах (USE_MOCK не влияет)
- **relay_controller.py** — API + context manager + интерактивный режим
- **tegam_real.py** — RS-232 парсер (исправлен парсер mOhm/MOhm)
- **tegam_mock.py** — реалистичный мок (R0–R19, нативные единицы, шум ±5)
- **measure_with_uncertainty()** — GUM Type A: mean, s(n-1), u=s/√n, U=2u (k=2)
- **config/config.xlsx** — 3 листа: Technicians, References, Settings
- **config/config_loader.py** — парсер конфига → CalibrationConfig / CalPoint / Technician
- **calibration/session.py** — state-машина + оркестратор + 3 режима + колбэки UI
- **ui/main_window.py** — полностью подключён к session.py:
  - Start/Stop реально работают
  - Таблица заполняется в реальном времени
  - Степпер обновляется по состоянию сессии
  - Индикаторы подключения приборов (зелёный/красный/серый) по событиям
  - Кнопки Confirm/Skip Adjust появляются при ADJUST
  - Dropdown выбора режима: Full / Verification Only / Adjust Only
  - Список техников загружается из config.xlsx
  - Event Log: Copy в буфер + Export в .txt файл с заголовком
  - После завершения калибровки сессия автоматически сбрасывается в IDLE
- **.gitignore** — покрытие Python, IDE, OS, Arduino
- **TegamCAL_Relay.ino** — скетч Arduino в репо
- **CLAUDE.md** — перекодирован в UTF-8 без BOM
- Полный цикл калибровки проходит за ~22 сек (4 точки × 5 измерений × 2 прогона)

## Что НЕ работает / не реализовано (❌)
- SQLite база данных
- Excel/PDF отчёты
- README пустой

## 🟡 TODO — Незавершённые задачи

### TODO 1: Adjust Only — кликабельные точки в левой панели
**Приоритет: средний**
Сейчас режим "Adjust Only" входит в состояние ADJUST и ждёт Stop,
но **UI не предоставляет способ переключать реле вручную**.
Сессия уже имеет метод `session.manual_relay(point_num)` —
осталось подключить его к UI:
- Сделать точки в левой панели кликабельными в состоянии ADJUST
- Клик по точке → `session.manual_relay(N)` → реле переключается
- Подсветить активную точку (active), остальные idle
- Добавить кнопку "All OFF" (R0)

### TODO 2: Отчёт Excel
**Приоритет: высокий** (нужен для демо)
- Кнопка "Save Report" появляется в состоянии REPORT
- AS FOUND + AS LEFT таблица в одном файле
- Колонки: nominal / measured / uncertainty / tolerance / PASS/FAIL
- Пометка "DEMO — 2-wire connection" на каждом отчёте

### TODO 3: SQLite база данных
**Приоритет: средний** (для Stage 2)
- Append-only: кто/что/когда
- Связка с отчётами по session_id

### TODO 4: Reconnect
**Приоритет: низкий**
- Кнопка Reconnect в шапке — пока заглушка
- Должна пинговать ?ID на оба прибора и обновлять badges

## 3 режима работы
| Режим | Этапы | Отчёт |
|-------|-------|-------|
| Full Calibration | AS FOUND → ADJUST (если FAIL) → AS LEFT → REPORT | Да |
| Verification Only | AS FOUND → REPORT | Да |
| Adjust Only | Только ADJUST (ручной контроль реле) | Нет |

## Структура проекта
```
TegamCAL/
├── CLAUDE.md
├── HANDOFF.md                ← этот файл
├── DECISIONS.md
├── UI_DECISIONS.md
├── ARDUINO_SETUP.md
├── COMPLIANCE_ROADMAP.md
├── .gitignore
├── main.py                   ← точка входа
├── config/
│   ├── __init__.py           ← USE_MOCK, COM_PORT, BAUDRATE, TIMEOUT
│   ├── config.xlsx           ← Technicians + References + Settings
│   └── config_loader.py      ← парсер → CalibrationConfig
├── calibration/
│   ├── __init__.py
│   └── session.py            ← state-машина + оркестратор
├── instruments/
│   ├── __init__.py
│   ├── tegam.py              ← абстракция (mock/real по USE_MOCK)
│   ├── tegam_mock.py
│   ├── tegam_real.py
│   └── relay_controller.py
├── ui/
│   ├── __init__.py
│   └── main_window.py        ← dashboard, подключён к session
├── tests/
│   ├── integration_test.py
│   └── test_session.py
└── TegamCAL_Relay.ino/
    └── TegamCAL_Relay.ino    ← скетч Arduino
```
