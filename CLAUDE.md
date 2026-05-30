# TegamCAL — Автоматизация калибровки Tegam 1750

## О проекте
Программа на Python для автоматизации калибровки омметра Tegam 1750.
Разработка ведётся в два этапа.

## Текущий этап: Прототип (Этап 1)
Цель — демонстрация возможностей руководству отдела.

### Оборудование (Этап 1)
- Tegam 1750 — омметр, подключение через COM порт (RS-232)
- Arduino Nano — управление реле через USB/COM порт
- Плата с 4 реле (китайская, синяя) — подключена к Arduino

### Стек
- Python + tkinter (визуальный интерфейс, Windows)
- pyserial — связь с Tegam 1750 и Arduino
- sqlite3 — локальная база данных калибровок
- reportlab или openpyxl — отчёты в PDF или Excel локально

### Функции Этап 1
1. Подключение к Tegam 1750 по COM порту — чтение показаний
2. Управление 4 реле через Arduino (переключение каналов)
3. Визуальный интерфейс tkinter — запуск калибровки, статус, лог
4. Сохранение отчёта локально (PDF или Excel)
5. Запись результатов в локальную БД SQLite
6. Для каждой точки калибровки выполнять 5 измерений
7. Рассчитывать неопределённость измерений по GUM Type A:
   - Среднее арифметическое (mean)
   - Стандартное отклонение выборки (s, делить на n-1)
   - Стандартная неопределённость u = s / sqrt(n)
   - Расширенная неопределённость U = 2 * u (k=2, 95%)
8. В отчёт добавить колонку Uncertainty:
   формат: 10.032 Ohm ± 0.004 Ohm (k=2, 95%)

## Следующий этап: Производство (Этап 2)
- Заменить Arduino на Keithley 2750 (GPIB или COM)
- Отчёты в сетевые папки предприятия
- БД SQL на сервере предприятия через WiFi

## Правила кода
- Язык: Python 3.10+
- Этап 1: визуальный интерфейс на английском, комментарии в коде на русском
- Этап 2: всё только на английском — интерфейс, комментарии, переменные
- Код писать модульно — отдельные файлы для: интерфейса, связи с приборами, БД, отчётов
- Сначала рабочий прототип, потом оптимизация
- Разработчик начинающий — код писать с подробными комментариями

## Структура проекта
```
TegamCAL/
├── CLAUDE.md
├── main.py          # запуск приложения
├── ui/              # интерфейс tkinter
├── instruments/     # связь с Tegam и Arduino
├── database/        # работа с SQLite
├── reports/         # генерация отчётов
└── README.md
```

## Calibration Process Flow

### Step 1 — Session Start
- Operator login: name, technician ID
- Enter instrument info: serial number, location
- Enter environmental conditions: temperature, humidity
- Date and time — automatic

### Step 2 — Load Configuration
- Load calibration_config file from program folder
- Contains: reference standards, tolerance limits, relay mapping
- Updated once per year after reference standards recalibration

### Step 3 — Warmup Notice
- Information message only: "Is instrument warmed up 30 min?"
- Operator confirms, no blocking

### Step 4 — AS FOUND run (automatic)
- For each calibration point:
  - Arduino switches relay automatically
  - Take 5 measurements
  - Calculate GUM Type A uncertainty
  - Compare result against tolerance limits
- Result: table with all points + PASS/FAIL per point

### Step 5 — Calibration (semi-automatic, only if needed)
- Triggered if any point FAIL in AS FOUND
- Screen shows manual relay control buttons
- Screen shows which nominal value Tegam is requesting
- Technician clicks relay button on screen
- Technician presses ENTER on Tegam front panel
- Repeat for each calibration point

### Step 6 — AS LEFT run (automatic)
- Same as AS FOUND run
- Performed after calibration

### Step 7 — Report Generation
- Combined report: AS FOUND + AS LEFT
- Columns: nominal / measured / uncertainty / tolerance / PASS/FAIL
- Overall status: PASS if all points within tolerance
- Next calibration date
- Save to: local PDF + local SQLite database

### Hardware Notes
- Stage 1 prototype: Arduino Nano + 4-relay board, 2-wire connection
- Stage 1 limitation: 2-wire adds lead resistance error (demo only)
- Stage 2 production: Keithley 2750 switcher, 4-wire Kelvin connection
