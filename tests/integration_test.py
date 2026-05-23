"""
Integration test: full chain without UI.

Arduino (real, COM4) + Tegam (mock, USE_MOCK=True in config.py).
Run from project root:  python tests/integration_test.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instruments.relay_controller import RelayController
from instruments.tegam import Tegam1750
from config import COM_PORT, BAUDRATE, TIMEOUT

ARDUINO_PORT = "COM4"
STABILIZATION_DELAY = 1.5

# Conversion factors: base Ohm → display unit (mirrors tegam.py)
_OHM_TO_UNIT = {"mOhm": 1e3, "Ohm": 1.0, "KOhm": 1e-3, "MOhm": 1e-6}
_DECIMALS = {"mOhm": 1, "Ohm": 3, "KOhm": 4, "MOhm": 4}


def format_nominal(nominal_ohm, display_unit):
    factor = _OHM_TO_UNIT.get(display_unit, 1.0)
    return f"{nominal_ohm * factor:.1f} {display_unit}"


def run():
    print("=== TegamCAL Integration Test ===\n")

    tegam = Tegam1750(port=COM_PORT, baudrate=BAUDRATE, timeout=TIMEOUT)

    with RelayController(port=ARDUINO_PORT) as relay:
        print(f"Arduino: {relay.get_id()}\n")

        for point in [1, 2, 3, 4]:
            relay_ok = relay.select_point(point)
            if hasattr(tegam, 'mock_set_resistor'):
                tegam.mock_set_resistor(relay.get_nominal(point))
            time.sleep(STABILIZATION_DELAY)

            result = tegam.measure_with_uncertainty()

            relay_status = "OK" if relay_ok else "FAIL"
            nominal_ohm = relay.get_nominal(point)

            if result is None:
                print(
                    f"Point {point} | Relay: {relay_status} | "
                    f"Nominal: {nominal_ohm} Ohm | ERROR: not enough valid readings"
                )
                continue

            d_unit = result["display_unit"]
            d_value = result["display_value"]
            d_U = result["display_uncertainty_expanded"]
            dec = _DECIMALS[d_unit]

            print(
                f"Point {point} | "
                f"Relay: {relay_status} | "
                f"Nominal: {format_nominal(nominal_ohm, d_unit)} | "
                f"Measured: {d_value:.{dec}f} {d_unit} | "
                f"U: ±{d_U:.{dec}f} {d_unit}"
            )

        relay.all_off()
        print("\nAll relays OFF.")

    tegam.close()
    print("Connections closed.")
    print("\n=== Test complete ===")


if __name__ == "__main__":
    run()
