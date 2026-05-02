import math
from config import USE_MOCK, COM_PORT, BAUDRATE, TIMEOUT

if USE_MOCK:
    from instruments.tegam_mock import Tegam1750Mock as _Tegam1750Base
else:
    from instruments.tegam_real import Tegam1750 as _Tegam1750Base


def _extract_display_unit(raw_string):
    import re
    m = re.search(r'[a-zA-Zµ]+[Oo]hm', raw_string)
    return m.group(0) if m else "Ohm"


class Tegam1750(_Tegam1750Base):
    """Tegam 1750 with GUM Type A uncertainty evaluation."""

    def measure_with_uncertainty(self, n=5):
        """Take n readings and compute GUM Type A uncertainty.

        Returns dict with keys:
            mean               — arithmetic mean (base Ohm)
            uncertainty_expanded — U = 2*u, k=2, 95%
            unit               — display unit extracted from raw string
            all_readings       — list of n valid float readings
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

        return {
            "mean": mean,
            "uncertainty_expanded": U,
            "unit": _extract_display_unit(first_raw) if first_raw else "Ohm",
            "all_readings": readings,
        }


__all__ = ["Tegam1750"]
