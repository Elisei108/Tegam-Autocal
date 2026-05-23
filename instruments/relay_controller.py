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
        startup = self.ser.readline().decode('ascii', errors='ignore').strip()
        if 'Ready' not in startup:
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


if __name__ == "__main__":
    with RelayController(port='COM4') as relay:
        print(relay.get_id())
        for point in [1, 2, 3, 4]:
            relay.select_point(point)
            print(f"Point {point}: {relay.get_nominal(point)} Ohm — measure now")
            time.sleep(2)
        relay.all_off()
