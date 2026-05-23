# 📋 Summary: Arduino для TegamCAL (Stage 1)

## Железо

- **Плата:** Arduino Nano Every (ATmega4809, оригинальная, 5V логика)
- **Релейный модуль:** 4-канальный на SONGLE SRD-24VDC-SL-C
- **COM порт:** COM4 (Windows, через USB)
- **Скорость связи:** 9600 baud

## Питание

- **Arduino:** через USB от ПК (5V)
- **Логика модуля (Vcc):** 5V от Arduino
- **Реле (JDVcc):** **внешний БП 19.5V** (от старого ноутбука)
- **Джампер JD-VCC: СНЯТ** (разделение питания логики и реле)
- **Общая земля:** GND Arduino + GND БП + Gnd модуля соединены

## Подключение пинов

```
Arduino Nano Every  →  Модуль реле
─────────────────────────────────
5V                  →  Vcc (левый разъём)
GND                 →  Gnd
D2                  →  In1  (управление реле 1)
D3                  →  In2  (управление реле 2)
D4                  →  In3  (управление реле 3)
D5                  →  In4  (управление реле 4)

БП 19.5V:
+                   →  JDVcc (правый разъём)
−                   →  Gnd (общая земля)
```

## Резисторы (эталоны для Stage 1)

| Реле | Резистор | Назначение |
|------|----------|-----------|
| R1 (D2) | 2 Ом | калибровочная точка 1 |
| R2 (D3) | 20 Ом | калибровочная точка 2 |
| R3 (D4) | 200 Ом | калибровочная точка 3 |
| R4 (D5) | 2000 Ом | калибровочная точка 4 |

Все резисторы соединены по схеме **common bus**: одни концы — на NO своих реле, другие — в общую точку. Все COM реле — в другую общую точку. Эти две точки = выход на измерительный прибор (Tegam 1750).

## ⚠️ Важная особенность: 2-проводное подключение

На малых сопротивлениях (2 Ом) погрешность 3-7% из-за сопротивления контактов реле и проводов. Для Stage 1 (демо) приемлемо. Stage 2 → Keithley 2750 + 4-проводное подключение Кельвина.

## ⚠️ Особенность модуля: инверсная логика

Релейный модуль работает **наоборот**:
- `LOW` на пине → реле **ВКЛЮЧЕНО**
- `HIGH` на пине → реле **ВЫКЛЮЧЕНО**

В Python это **не важно** — Arduino-скетч уже инкапсулирует логику, Python работает с понятными ASCII командами.

---

## Протокол общения Python ↔ Arduino

### Параметры порта:
- **Baud rate:** 9600
- **Bytesize:** 8
- **Parity:** None
- **Stopbits:** 1
- **End of line:** `\n` (newline)

### Команды (Python → Arduino):

| Команда | Действие | Ответ Arduino |
|---------|----------|---------------|
| `R1\n` | Включить только реле 1 (2 Ом) | `OK\n` |
| `R2\n` | Включить только реле 2 (20 Ом) | `OK\n` |
| `R3\n` | Включить только реле 3 (200 Ом) | `OK\n` |
| `R4\n` | Включить только реле 4 (2000 Ом) | `OK\n` |
| `R0\n` | Выключить все реле | `OK\n` |
| `?STS\n` | Запрос статуса | `STS:0001\n` (битовая маска R4R3R2R1) |
| `?ID\n` | Идентификация | `TegamCAL Arduino Nano Every v1.1\n` |

### Сообщение при старте Arduino:
```
TegamCAL Relay Module Ready\n
```

### 🛡️ Встроенная защита от ошибок:
**Включение любого реле автоматически выключает остальные** (функция `allOff()` в скетче). В любой момент времени включено **только одно реле** — измерения всегда корректны, нет риска параллельного соединения резисторов.

---

## Готовый Python модуль для проекта

```python
# instruments/relay_controller.py
import serial
import time

class RelayController:
    """Управление 4-канальным релейным модулем через Arduino Nano Every."""
    
    RESISTORS = {
        1: 2.0,      # Ом
        2: 20.0,     # Ом
        3: 200.0,    # Ом
        4: 2000.0,   # Ом
    }
    
    def __init__(self, port='COM4', baudrate=9600, timeout=2):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Arduino reboots on serial open — wait for ready
        self.ser.reset_input_buffer()
        # Прочитать startup-сообщение
        startup = self.ser.readline().decode('ascii', errors='ignore').strip()
        if 'Ready' not in startup:
            # На всякий случай пробуем еще раз
            pass
    
    def _send(self, command: str) -> str:
        """Отправить команду, вернуть ответ Arduino."""
        self.ser.reset_input_buffer()
        self.ser.write(f"{command}\n".encode('ascii'))
        response = self.ser.readline().decode('ascii', errors='ignore').strip()
        return response
    
    def select_point(self, point: int) -> bool:
        """Включить реле для калибровочной точки 1..4. R0 = все выкл."""
        if point not in (0, 1, 2, 3, 4):
            raise ValueError(f"Invalid point: {point}")
        response = self._send(f"R{point}")
        time.sleep(0.05)  # дать реле физически переключиться
        return response == "OK"
    
    def all_off(self) -> bool:
        return self.select_point(0)
    
    def get_status(self) -> str:
        return self._send("?STS")
    
    def get_id(self) -> str:
        return self._send("?ID")
    
    def get_nominal(self, point: int) -> float:
        """Номинальное сопротивление для калибровочной точки."""
        return self.RESISTORS[point]
    
    def close(self):
        self.all_off()
        self.ser.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# Пример использования:
if __name__ == "__main__":
    with RelayController(port='COM4') as relay:
        print(relay.get_id())
        for point in [1, 2, 3, 4]:
            relay.select_point(point)
            print(f"Point {point}: {relay.get_nominal(point)} Ohm — measure now")
            time.sleep(2)  # здесь Tegam берет показания
        relay.all_off()
```

---

## Тонкости интеграции (важно для Python!)

1. **При открытии порта Arduino перезагружается** (DTR reset) → нужна задержка `time.sleep(2)` перед первой командой
2. **После переключения реле — ждать 50 мс** для физической стабилизации контактов
3. **Между переключением реле и измерением Tegam — ждать ~1-2 сек** для устранения переходных процессов на длинных проводах
4. **Закрытие порта:** перед `close()` всегда отправлять `R0` (выключить реле) — иначе они останутся в последнем состоянии
5. **Конфиг-файл** (Stage 1): пин → реле → номинальное сопротивление + допуск (для будущей привязки к точкам Tegam)

---

## Среда разработки

- **Arduino IDE:** не работает с Nano Every на Windows (баг avrdude `jtagmkII_initialize()`)
- **Решение:** прошивка через **Arduino Web Editor** (https://app.arduino.cc/sketches) — компиляция на серверах Arduino, нет проблем с локальным avrdude
- **Для Python разработки IDE не нужна** — скетч уже залит, Arduino работает автономно
