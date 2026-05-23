import time
import random
import re


class Tegam1750Mock:
    def __init__(self, port="MOCK_PORT", baudrate=9600, timeout=2):
        print(f"[MOCK] Виртуальный Tegam 1750 (RS-232) 'подключен' к {port}.")
        self.device = True
        self.timeout = timeout

        # Физическое состояние "железа"
        self.connected_resistor = 10.032
        self.is_open_wire = False

        self._initialize_device()

    def _initialize_device(self):
        """Сброс прибора к заводским настройкам (команда I)"""
        self.current_range = 15
        self.in_error_state = False
        self.buffer = ""
        print("[MOCK] Прибор инициализирован (Лампочка ERROR погасла, если горела).")

    def send_command(self, command):
        """Парсер команд RS-232 (согласно Таблице 5.3 мануала)"""
        if not self.device: return

        cmd_str = command.strip().upper()

        # Команда инициализации и сброса ошибок обрабатывается безусловно
        if 'I' in cmd_str:
            self._initialize_device()
            return

        # Если прибор в ошибке (горит лампочка), он игнорирует всё, кроме I
        if self.in_error_state:
            print("[MOCK] Прибор в состоянии ERROR. Команда проигнорирована. Ожидается 'I'.")
            return

        # Триггер измерения (буква E)
        if 'E' in cmd_str:
            self.buffer = self._generate_reading()
            return

        # Настройка параметров (требует подтверждения 'X')
        if 'X' in cmd_str:
            sub_commands = cmd_str.split('X')[:-1]

            for sub_cmd in sub_commands:
                match_r = re.search(r'R(\d+)', sub_cmd)
                if match_r:
                    range_code = int(match_r.group(1))
                    if 0 <= range_code <= 14:
                        self.current_range = range_code
                        print(f"[MOCK] Диапазон установлен на R{self.current_range}")
                    else:
                        self._trigger_error()
                        return
                    continue

                match_y = re.search(r'Y(\d+)', sub_cmd)
                if match_y:
                    continue

                if not sub_cmd.strip():
                    continue

                if not match_r and not match_y:
                    self._trigger_error()
                    return

            time.sleep(0.3)  # Имитация времени на переключение внутренних реле

    def _trigger_error(self):
        self.in_error_state = True
        print("[MOCK-ERROR] Неверная команда! Загорелась лампочка ERROR. Прибор ушел в анабиоз.")

    def get_raw_reading(self):
        """Чтение буфера по интерфейсу RS-232"""
        if not self.device: return None

        if self.in_error_state or not self.buffer:
            time.sleep(self.timeout)
            return ""

        result = self.buffer
        self.buffer = ""
        return result

    def _generate_reading(self):
        time.sleep(random.uniform(0.05, 0.25))

        if self.is_open_wire:
            return "29.999  MOhm"

        r = self.connected_resistor

        if r <= 2.0:
            noise = random.randint(-5, 5) * 0.0001
            val = round(r + noise, 4)
            return f"  {val:.4f}  Ohm"
        elif r <= 20.0:
            noise = random.randint(-5, 5) * 0.001
            val = round(r + noise, 3)
            return f" {val:.3f}  Ohm"
        elif r <= 200.0:
            noise = random.randint(-5, 5) * 0.01
            val = round(r + noise, 2)
            return f"{val:.2f}   Ohm"
        elif r <= 2000.0:
            noise = random.randint(-5, 5) * 0.1
            val_k = round((r + noise) / 1000, 4)
            return f"  {val_k:.4f} KOhm"
        else:
            noise = random.randint(-5, 5) * 1.0
            val_k = round((r + noise) / 1000, 3)
            return f" {val_k:.3f} KOhm"

    def parse_reading(self, raw_string):
        if not raw_string:
            return None, "Нет ответа / Таймаут"

        clean_string = raw_string.strip()
        if "2.9999" in clean_string or "29.999" in clean_string:
            return float('inf'), "OPEN WIRE / OVERLOAD"

        match = re.search(r"([+-]?\d+\.?\d*)\s*([a-zA-Z]+)?", clean_string)
        if match:
            value = float(match.group(1))
            unit_upper = (match.group(2) or "").upper()

            multiplier = 1.0
            if "UOHM" in unit_upper or "µOHM" in unit_upper:
                multiplier = 1e-6
            elif "MOHM" in unit_upper:
                multiplier = 1e6
            elif "KOHM" in unit_upper:
                multiplier = 1e3
            elif "M" in match.group(2) and "Ohm" in match.group(2):
                multiplier = 1e-3

            return value * multiplier, "OK"

        return None, f"Неизвестный формат: {raw_string}"

    def set_range(self, range_code):
        self.send_command(f"R{range_code}X")

    def measure(self):
        self.send_command("E")
        raw = self.get_raw_reading()
        val, status = self.parse_reading(raw)
        return val, status, raw

    def close(self):
        self.device = False

    # --- Управление стендом для тестов ---
    def mock_set_resistor(self, ohms):
        """Симуляция подключения эталона"""
        self.connected_resistor = ohms
        self.is_open_wire = False

    def mock_set_open_wire(self):
        """Симуляция обрыва цепи"""
        self.is_open_wire = True
