from config import USE_MOCK, COM_PORT, BAUDRATE, TIMEOUT

if USE_MOCK:
    from instruments.tegam_mock import Tegam1750Mock as Tegam1750
else:
    from instruments.tegam_real import Tegam1750

__all__ = ["Tegam1750"]
