import math
import re
from config import USE_MOCK, COM_PORT, BAUDRATE, TIMEOUT

if USE_MOCK:
    from instruments.tegam_mock import Tegam1750Mock as _Tegam1750Base
else:
    from instruments.tegam_real import Tegam1750 as _Tegam1750Base

# Conversion factors: base Ohm → native display unit
_OHM_TO_UNIT = {"mOhm": 1e3, "Ohm": 1.0, "KOhm": 1e-3, "MOhm": 1e-6}
_DISPLAY_DECIMALS = {"mOhm": 1, "Ohm": 3, "KOhm": 4, "MOhm": 4}


def _native_unit(raw_string):
    """Return (unit, factor) where factor converts base-Ohm → native unit."""
    m = re.search(r'(KOhm|MOhm|mOhm|Ohm)', raw_string)
    unit = m.group(1) if m else "Ohm"
    return unit, _OHM_TO_UNIT.get(unit, 1.0)


class Tegam1750(_Tegam1750Base):
    """Tegam 1750 with GUM Type A uncertainty evaluation."""

    def measure_with_uncertainty(self, n=5):
        """Take n readings and compute GUM Type A uncertainty.

        Returns dict with keys:
            mean                        — arithmetic mean, base Ohm (for DB / calculations)
            uncertainty_expanded        — U = 2*u, k=2, 95%, base Ohm
            unit                        — "Ohm" (base unit for internal use)
            all_readings                — list of n valid readings in base Ohm
            display_unit                — native Tegam unit ("Ohm", "KOhm", "MOhm")
            display_value               — mean in display_unit
            display_uncertainty_expanded — U in display_unit
        Returns None if fewer than 2 valid readings obtained.
        """
        readings = []
        first_raw = None

        for _ in range(n):
            val, status, raw = self.measure()
            if status == "OK" and val is not None and val != float("inf"):
                readings.append(val)
                if first_raw is None and raw:
                    first_raw = raw

        if len(readings) < 2:
            return None

        mean = sum(readings) / len(readings)
        s = math.sqrt(sum((x - mean) ** 2 for x in readings) / (len(readings) - 1))
        u = s / math.sqrt(len(readings))
        U = 2 * u

        d_unit, factor = _native_unit(first_raw) if first_raw else ("Ohm", 1.0)

        return {
            "mean": mean,
            "uncertainty_expanded": U,
            "unit": "Ohm",
            "all_readings": readings,
            "display_unit": d_unit,
            "display_value": mean * factor,
            "display_uncertainty_expanded": U * factor,
        }


__all__ = ["Tegam1750"]
