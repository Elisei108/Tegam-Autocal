import serial
import time
import re


class Tegam1750:
    def __init__(self, port, baudrate=9600, timeout=2):
        try:
            self.device = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout
            )
            print(f"Успешное подключение к порту {port}.")
            # Установка терминаторов вывода в <CR><LF> и очистка
            self.send_command("Y0X")

        except serial.SerialException as e:
            print(f"Ошибка подключения к COM-порту: {e}")
            self.device = None

    def send_command(self, command):
        if self.device and self.device.is_open:
            full_command = f"{command}\r\n".encode('ascii')
            self.device.write(full_command)
            time.sleep(0.1)

    def get_raw_reading(self):
        if self.device and self.device.is_open:
            self.device.reset_input_buffer()
            self.send_command("E")
            raw_response = self.device.readline().decode('ascii').strip()
            return raw_response
        return None

    def set_range(self, range_code):
        """Установка диапазона."""
        command = f"R{range_code}X"
        self.send_command(command)
        print(f"Отправлена команда смены диапазона: {command}")
        time.sleep(0.5)  # Пауза на переключение реле внутри самого прибора

    def parse_reading(self, raw_string):
        if not raw_string:
            return None, "Нет ответа"

        clean_string = raw_string.strip()

        if "2.9999" in clean_string or "29.999" in clean_string:
            return float('inf'), "OPEN WIRE / OVERLOAD"

        match = re.search(r"([+-]?\d+\.?\d*)\s*([a-zA-Z]+)?", clean_string)

        if match:
            value_str = match.group(1)
            unit_str = match.group(2)

            try:
                value = float(value_str)
            except ValueError:
                return None, f"Ошибка конвертации значения: {value_str}"

            multiplier = 1.0
            if unit_str:
                unit_upper = unit_str.upper()
                # ВАЖНО: проверяем mOhm (миллиОм) ДО MOhm (мегаОм)!
                # Tegam 1750 возвращает строку вида "1.2345 mOhm" — маленькая 'm'
                # Если проверять unit_upper, то и 'mOhm' и 'MOhm' дают 'MOHM' — неразличимы.
                # Поэтому сначала проверяем оригинальный unit_str (case-sensitive).
                if "uOhm" in unit_str or "µOhm" in unit_str or "uohm" in unit_str:
                    multiplier = 1e-6   # микроОм
                elif "mOhm" in unit_str or "mohm" in unit_str:
                    multiplier = 1e-3   # миллиОм (маленькая m!)
                elif "MOhm" in unit_str or "MOHM" in unit_upper:
                    multiplier = 1e6    # мегаОм (большая M)
                elif "kOhm" in unit_str or "KOHM" in unit_upper:
                    multiplier = 1e3    # килоОм
                elif "Ohm" in unit_str or "OHM" in unit_upper:
                    multiplier = 1.0    # Ом

            final_value = value * multiplier
            return final_value, "OK"

        return None, f"Неизвестный формат: {raw_string}"

    def measure(self):
        raw = self.get_raw_reading()
        val, status = self.parse_reading(raw)
        return val, status, raw

    def close(self):
        if self.device and self.device.is_open:
            self.device.close()
            print("Порт закрыт.")


if __name__ == "__main__":
    # ВАЖНО: Укажи здесь свой COM-порт
    PORT_NAME = 'COM3'

    tegam = Tegam1750(port=PORT_NAME)

    if tegam.device and tegam.device.is_open:
        try:
            print("\nНачинаем опрос прибора. Снимаем 5 показаний...")
            tegam.set_range(13)
            for i in range(5):
                val, status, raw = tegam.measure()
                print(f"[{i + 1}] Сырой ответ: '{raw}' | Распарсено: {val} Ом | Статус: {status}")
                time.sleep(1)
        finally:
            tegam.close()
