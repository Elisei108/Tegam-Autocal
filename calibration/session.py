"""
calibration/session.py — Оркестратор калибровки TegamCAL.

Дирижирует всем процессом: реле → измерения → GUM → PASS/FAIL → UI.

Состояния (state-машина):
    IDLE
      ↓  start_session()
    AS_FOUND          — автоматический прогон всех 4 точек
      ↓  _run_phase() завершён
    ADJUST            — если есть FAIL: оператор подстраивает прибор
      ↓  confirm_adjust() или skip_adjust()
    AS_LEFT           — автоматический прогон всех 4 точек после подстройки
      ↓  _run_phase() завершён
    REPORT            — данные готовы, ждём сохранения отчёта
      ↓  finish_session()
    IDLE

Связь с UI — через колбэки (callback functions).
Session ничего не знает о tkinter. UI сам передаёт функции при старте.

Потоки: измерения идут в отдельном Thread, колбэки вызываются
через _ui_call() который безопасно передаёт вызов в главный поток UI.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from config import USE_MOCK, COM_PORT, BAUDRATE, TIMEOUT
from config.config_loader import load_config, CalibrationConfig, CalPoint
from instruments.tegam import Tegam1750
from instruments.relay_controller import RelayController


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные структуры данных
# ──────────────────────────────────────────────────────────────────────────────

class State(Enum):
    """Возможные состояния сессии калибровки."""
    IDLE      = auto()
    AS_FOUND  = auto()
    ADJUST    = auto()
    AS_LEFT   = auto()
    REPORT    = auto()
    ABORTED   = auto()


class Mode(Enum):
    """Режимы работы сессии — какие этапы выполнять.

    FULL          — Полный цикл: AS FOUND → ADJUST (если FAIL) → AS LEFT → REPORT
    VERIFICATION  — Только AS FOUND → REPORT (без подстройки)
    ADJUST_ONLY   — Только режим подстройки — свободный выбор реле
                    (оператор кликает по точкам в левой панели, без измерений)
    """
    FULL         = "Full Calibration"
    VERIFICATION = "Verification Only"
    ADJUST_ONLY  = "Adjust Only"


@dataclass
class PointResult:
    """Результат измерения одной калибровочной точки."""
    point_num:     int               # номер точки 1..4
    nominal_ohm:   float             # номинал из конфига
    ref_value_ohm: float             # значение эталона из конфига
    readings:      List[float]       # список из N сырых показаний в Ом
    mean_ohm:      float             # среднее арифметическое
    u_expanded:    float             # расширенная неопределённость U (k=2)
    display_unit:  str               # "Ohm" / "KOhm" / "MOhm"
    display_value: float             # среднее в единицах отображения
    display_u:     float             # U в единицах отображения
    tolerance_ohm: float             # допуск ±X Ом из конфига
    passed:        bool              # True = PASS, False = FAIL
    timestamp:     datetime = field(default_factory=datetime.now)


@dataclass
class SessionData:
    """Данные всей сессии калибровки — собирается по ходу работы."""
    operator:       str = ""
    serial_no:      str = ""
    temperature:    str = ""
    humidity:       str = ""
    mode:           "Mode" = None   # режим сессии (FULL/VERIFICATION/ADJUST_ONLY)
    started_at:     Optional[datetime] = None
    finished_at:    Optional[datetime] = None
    as_found:       List[PointResult] = field(default_factory=list)
    as_left:        List[PointResult] = field(default_factory=list)
    adjust_done:    bool = False      # была ли подстройка


# ──────────────────────────────────────────────────────────────────────────────
# Главный класс
# ──────────────────────────────────────────────────────────────────────────────

class CalibrationSession:
    """
    Оркестратор калибровки.

    Как использовать:
        session = CalibrationSession()
        session.on_state_change  = lambda s: ...
        session.on_measurement   = lambda pt, idx, val, unit: ...
        session.on_point_done    = lambda pt, result: ...
        session.on_phase_done    = lambda phase, results: ...
        session.on_error         = lambda msg: ...
        session.on_log           = lambda level, msg: ...

        session.start_session(operator="Иванов", serial_no="001", ...)
    """

    def __init__(self):
        # --- Состояние ---
        self._state = State.IDLE
        self._lock  = threading.Lock()   # защита от гонок между потоками
        self._abort = threading.Event()  # сигнал остановки

        # --- Данные сессии ---
        self.session_data = SessionData()
        self._config: Optional[CalibrationConfig] = None

        # --- Инструменты ---
        self._tegam: Optional[Tegam1750] = None
        self._relay: Optional[RelayController] = None

        # --- UI root (для безопасных вызовов из потока) ---
        # Устанавливается извне: session.ui_root = app
        self.ui_root = None

        # ── Колбэки (устанавливаются извне) ──────────────────────────────────
        # Вызывается когда меняется состояние state-машины
        self.on_state_change:  Callable[[State], None]                    = lambda s: None
        # Вызывается после каждого одиночного измерения
        # Аргументы: номер точки (0-based), индекс измерения (0..4), значение, единица
        self.on_measurement:   Callable[[int, int, float, str], None]     = lambda *a: None
        # Вызывается когда точка полностью измерена (5 показаний + GUM)
        self.on_point_done:    Callable[[int, PointResult], None]         = lambda *a: None
        # Вызывается когда весь фазовый прогон (AS FOUND или AS LEFT) завершён
        self.on_phase_done:    Callable[[str, List[PointResult]], None]   = lambda *a: None
        # Вызывается при ошибке связи или другой критической ошибке
        self.on_error:         Callable[[str], None]                      = lambda m: None
        # Вызывается для записи в лог UI
        self.on_log:           Callable[[str, str], None]                 = lambda l, m: None
        # Вызывается когда меняется состояние подключения прибора
        # Аргументы: 'tegam'|'arduino', 'ok'|'error'|'unknown'
        self.on_instrument_status: Callable[[str, str], None]            = lambda i, s: None

    # ──────────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state

    def start_session(self, operator: str, serial_no: str,
                      temperature: str, humidity: str,
                      mode: "Mode" = None,
                      config_path: str = None):
        """
        Запустить новую сессию калибровки.
        Параметр mode определяет какие этапы выполнять:
          Mode.FULL         — AS FOUND → ADJUST (если FAIL) → AS LEFT → REPORT
          Mode.VERIFICATION — только AS FOUND → REPORT
          Mode.ADJUST_ONLY  — только режим подстройки (без измерений)
        """
        if self._state != State.IDLE:
            self._log("WARN", "Session already running — stop it first")
            return

        # По умолчанию — полный цикл
        if mode is None:
            mode = Mode.FULL

        # Сохраняем данные сессии
        self.session_data = SessionData(
            operator    = operator,
            serial_no   = serial_no,
            temperature = temperature,
            humidity    = humidity,
            mode        = mode,
            started_at  = datetime.now(),
        )

        self._abort.clear()

        # Запускаем в отдельном потоке чтобы не замораживать UI
        t = threading.Thread(target=self._session_thread,
                             args=(config_path,), daemon=True)
        t.start()

    def abort(self):
        """Остановить калибровку в любой момент (нажатие Stop)."""
        self._log("WARN", "Abort requested by operator")
        self._abort.set()

    def confirm_adjust(self):
        """
        Оператор нажал ENTER после подстройки прибора.
        Разблокирует поток, который ждёт в состоянии ADJUST.
        """
        if self._state == State.ADJUST:
            self._adjust_event.set()

    def skip_adjust(self):
        """Пропустить подстройку и перейти сразу к AS LEFT."""
        if self._state == State.ADJUST:
            self._log("WARN", "Adjust skipped by operator")
            self.session_data.adjust_done = False
            self._adjust_event.set()

    # ──────────────────────────────────────────────────────────────────────────
    # Основной поток сессии
    # ──────────────────────────────────────────────────────────────────────────

    def _session_thread(self, config_path: str):
        """Выполняется в отдельном потоке. Сценарий зависит от выбранного режима."""
        try:
            mode = self.session_data.mode

            # Шаг 1: загрузить конфиг
            self._log("INFO", f"Loading configuration... (mode: {mode.value})")
            try:
                self._config = load_config(config_path)
            except Exception as e:
                self._error(f"Failed to load config: {e}")
                return

            n = self._config.get_setting("N_READINGS", 5)
            delay = float(self._config.get_setting("STABILIZATION_DELAY_S", 1.5))
            self._log("INFO", f"Config loaded — {len(self._config.points)} cal points, "
                              f"N={n}, stabilisation delay={delay}s")

            # Шаг 2: подключить приборы
            if not self._connect_instruments():
                return

            # Шаг 3: ветвление по режимам
            if mode == Mode.FULL:
                self._run_full_cycle(n, delay)
            elif mode == Mode.VERIFICATION:
                self._run_verification(n, delay)
            elif mode == Mode.ADJUST_ONLY:
                self._run_adjust_only()
            else:
                self._error(f"Unknown mode: {mode}")
                return

        except Exception as e:
            self._error(f"Unexpected error in session thread: {e}")
        finally:
            self._disconnect_instruments()
            if self._state not in (State.REPORT, State.ABORTED):
                self._set_state(State.IDLE)

    # ───────────────────────────────────────────────────────────────────────
    # Сценарии по режимам
    # ───────────────────────────────────────────────────────────────────────

    def _run_full_cycle(self, n: int, delay: float):
        """Полный цикл: AS FOUND → ADJUST (если FAIL) → AS LEFT → REPORT."""
        # AS FOUND
        self._set_state(State.AS_FOUND)
        self._log("INFO", "=== AS FOUND run started ===")
        as_found_results = self._run_phase("AS FOUND", n, delay)
        if self._abort.is_set(): return
        self.session_data.as_found = as_found_results
        self._ui_call(self.on_phase_done, "AS FOUND", as_found_results)

        # ADJUST (только если есть FAIL)
        failed_points = [r for r in as_found_results if not r.passed]
        if failed_points:
            self._log("WARN",
                f"AS FOUND: {len(failed_points)} point(s) FAIL — entering ADJUST mode")
            self._run_adjust(failed_points)
        else:
            self._log("PASS", "AS FOUND: all points PASS — skipping ADJUST")
        if self._abort.is_set(): return

        # AS LEFT
        self._set_state(State.AS_LEFT)
        self._log("INFO", "=== AS LEFT run started ===")
        as_left_results = self._run_phase("AS LEFT", n, delay)
        if self._abort.is_set(): return
        self.session_data.as_left = as_left_results
        self.session_data.finished_at = datetime.now()
        self._ui_call(self.on_phase_done, "AS LEFT", as_left_results)

        # REPORT
        self._set_state(State.REPORT)
        self._log("INFO", "=== Calibration complete — ready for report ===")

    def _run_verification(self, n: int, delay: float):
        """Режим верификации: только AS FOUND → REPORT.
        Используется когда нужно проверить прибор без подстройки
        (например, решить — оставлять в работе или в ремонт).
        Данные AS FOUND записываются также в as_left,
        чтобы отчёт корректно отображал ситуацию "как было = как оставили".
        """
        self._set_state(State.AS_FOUND)
        self._log("INFO", "=== VERIFICATION run started (AS FOUND only) ===")
        as_found_results = self._run_phase("AS FOUND", n, delay)
        if self._abort.is_set(): return
        self.session_data.as_found = as_found_results
        self.session_data.finished_at = datetime.now()
        self._ui_call(self.on_phase_done, "AS FOUND", as_found_results)

        # REPORT
        self._set_state(State.REPORT)
        self._log("INFO", "=== Verification complete — ready for report ===")

    def _run_adjust_only(self):
        """Режим только подстройки: без измерений, без отчёта.
        Сессия входит в состояние ADJUST и ждёт пока оператор нажмёт Stop.
        Переключение реле в этом режиме должно быть реализовано в UI —
        сессия предоставляет метод manual_relay() для этого.
        """
        self._set_state(State.ADJUST)
        self._log("WARN",
            "=== ADJUST ONLY mode — manual relay control. "
            "Press Stop when finished. ===")

        # Активируем механизм ожидания (на случай если UI позволит confirm)
        self._adjust_event = threading.Event()

        # Ждём Stop или confirm_adjust
        while not self._adjust_event.is_set() and not self._abort.is_set():
            time.sleep(0.1)

        self._log("INFO", "ADJUST ONLY mode finished")
        # В режиме ADJUST_ONLY нет отчёта — выходим в IDLE
        self.session_data.finished_at = datetime.now()

    def manual_relay(self, point_num: int) -> bool:
        """Ручное переключение реле оператором в режиме ADJUST.
        Используется UI когда оператор кликает по точке в левой панели.
        Работает только в состоянии ADJUST. point_num: 1..4 (или 0 для выкл)
        """
        if self._state != State.ADJUST:
            self._log("WARN", "manual_relay() ignored — not in ADJUST state")
            return False
        if self._relay is None:
            self._log("ERR", "manual_relay() failed — relay not connected")
            return False
        try:
            ok = self._relay.select_point(point_num)
            if point_num == 0:
                self._log("INFO", "Manual: all relays OFF")
            else:
                cp = self._config.get_point(point_num)
                self._log("INFO", f"Manual: relay R{point_num} ON ({cp.nominal_ohm} Ohm)")
            return ok
        except Exception as e:
            self._log("ERR", f"manual_relay() error: {e}")
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # Фазовый прогон (AS FOUND / AS LEFT)
    # ──────────────────────────────────────────────────────────────────────────

    def _run_phase(self, phase_name: str,
                   n_readings: int,
                   stabilisation_s: float) -> List[PointResult]:
        """
        Прогнать все 4 калибровочные точки.
        Возвращает список PointResult (4 штуки).
        """
        results = []

        for cal_point in self._config.points:
            if self._abort.is_set():
                break

            pt_idx = cal_point.point - 1   # 0-based для UI
            self._log("INFO", f"[{phase_name}] Point {cal_point.point} "
                               f"— {cal_point.nominal_ohm} Ohm "
                               f"(relay {cal_point.relay})")

            # Переключить реле
            ok = self._switch_relay(cal_point)
            if not ok:
                self._log("WARN", f"Relay {cal_point.relay} did not confirm — continuing anyway")

            # Ждём стабилизации цепи
            self._sleep_with_abort(stabilisation_s)
            if self._abort.is_set():
                break

            # Синхронизируем mock с реле (только в режиме USE_MOCK)
            if USE_MOCK and hasattr(self._tegam, "mock_set_resistor"):
                self._tegam.mock_set_resistor(cal_point.nominal_ohm)

            # Устанавливаем диапазон Tegam
            self._tegam.set_range(cal_point.range_code)

            # Снимаем N показаний
            readings_ohm = []
            for i in range(n_readings):
                if self._abort.is_set():
                    break

                val, status, raw = self._tegam.measure()

                if status != "OK" or val is None or val == float("inf"):
                    self._log("WARN",
                        f"  Reading {i+1}: bad reading — status={status}, raw='{raw}'")
                    continue

                readings_ohm.append(val)

                # Сообщаем UI о каждом показании
                # Конвертируем в единицы отображения для таблицы
                disp_val = self._to_display(val, cal_point.display_unit)
                self._ui_call(self.on_measurement,
                              pt_idx, i, disp_val, cal_point.display_unit)

                self._log("INFO",
                    f"  Reading {i+1}: {disp_val:.{self._decimals(cal_point.display_unit)}f}"
                    f" {cal_point.display_unit}")

            if self._abort.is_set():
                break

            # Недостаточно показаний для GUM
            if len(readings_ohm) < 2:
                self._log("ERR",
                    f"Point {cal_point.point}: only {len(readings_ohm)} valid reading(s) — "
                    "need at least 2 for GUM. Marking point as FAIL.")
                # Создаём PointResult со статусом FAIL — точка НЕ должна молча выпадать
                # из отчёта. Это важно для метрологии: прибор отказал — это FAIL,
                # а не причина прятать точку.
                fail_result = PointResult(
                    point_num     = cal_point.point,
                    nominal_ohm   = cal_point.nominal_ohm,
                    ref_value_ohm = cal_point.ref_value_ohm,
                    readings      = readings_ohm,         # может быть [] или [одно значение]
                    mean_ohm      = float("nan"),
                    u_expanded    = float("nan"),
                    display_unit  = cal_point.display_unit,
                    display_value = float("nan"),
                    display_u     = float("nan"),
                    tolerance_ohm = cal_point.tolerance_ohm(),
                    passed        = False,                # явно FAIL
                )
                results.append(fail_result)
                self._ui_call(self.on_point_done, pt_idx, fail_result)
                continue

            # GUM Type A
            result = self._compute_gum(cal_point, readings_ohm)
            results.append(result)

            # Сообщаем UI о завершении точки
            self._ui_call(self.on_point_done, pt_idx, result)

            status_str = "PASS" if result.passed else "FAIL"
            self._log(
                "PASS" if result.passed else "FAIL",
                f"Point {cal_point.point} {status_str}: "
                f"mean={result.display_value:.{self._decimals(result.display_unit)}f}"
                f" {result.display_unit}, "
                f"U=±{result.display_u:.{self._decimals(result.display_unit)}f}, "
                f"tol=±{self._to_display(result.tolerance_ohm, result.display_unit):.{self._decimals(result.display_unit)}f}"
            )

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Подстройка (ADJUST)
    # ──────────────────────────────────────────────────────────────────────────

    def _run_adjust(self, failed_points: List):
        """
        Переключить реле на первую проваленную точку и ждать подтверждения оператора.
        Оператор физически подстраивает прибор и нажимает ENTER (или кнопку в UI).
        """
        self._adjust_event = threading.Event()
        self._set_state(State.ADJUST)

        # Переключаем реле на первую проваленную точку
        # В полной реализации можно по очереди проходить все FAIL-точки
        first_fail = failed_points[0]
        cal_point = self._config.get_point(first_fail.point_num)
        self._switch_relay(cal_point)

        self._log("WARN",
            f"ADJUST: relay switched to Point {cal_point.point} "
            f"({cal_point.nominal_ohm} Ohm). "
            "Press ENTER on Tegam panel, then confirm in UI.")

        # Ждём пока оператор нажмёт confirm_adjust() или skip_adjust()
        # Или пока не нажмут Stop (abort)
        while not self._adjust_event.is_set() and not self._abort.is_set():
            time.sleep(0.1)

        self.session_data.adjust_done = True

    # ──────────────────────────────────────────────────────────────────────────
    # Подключение / отключение приборов
    # ──────────────────────────────────────────────────────────────────────────

    def _connect_instruments(self) -> bool:
        """Подключить приборы. Вернуть False если не удалось.

        Arduino нужен всегда — реле должны щёлкать.
        Tegam нужен только если будут измерения (Full / Verification).
        В режиме Adjust Only Tegam не подключаем.
        """
        mode = self.session_data.mode
        need_tegam = (mode != Mode.ADJUST_ONLY)

        # --- Tegam: реальный или мок (не нужен в Adjust Only) ---
        if need_tegam:
            self._log("INFO", f"Connecting Tegam 1750 (USE_MOCK={USE_MOCK})...")
            try:
                self._tegam = Tegam1750(port=COM_PORT, baudrate=BAUDRATE, timeout=TIMEOUT)
                self._log("INFO", "Tegam 1750 connected")
                self._ui_call(self.on_instrument_status, "tegam", "ok")
            except Exception as e:
                self._ui_call(self.on_instrument_status, "tegam", "error")
                self._error(f"Cannot connect Tegam: {e}")
                return False
        else:
            self._log("INFO", "Tegam 1750 skipped (Adjust Only mode — no measurements)")
            self._ui_call(self.on_instrument_status, "tegam", "unknown")

        # --- Arduino: всегда реальный ---
        arduino_port = self._config.get_setting("ARDUINO_PORT", "COM4")
        self._log("INFO", f"Connecting Arduino relay controller on {arduino_port}...")
        try:
            self._relay = RelayController(port=arduino_port, baudrate=9600)
            self._log("INFO", f"Arduino connected: {self._relay.get_id()}")
            self._ui_call(self.on_instrument_status, "arduino", "ok")
        except Exception as e:
            self._ui_call(self.on_instrument_status, "arduino", "error")
            self._error(f"Cannot connect Arduino on {arduino_port}: {e}")
            return False

        return True

    def _disconnect_instruments(self):
        """Безопасно закрыть все соединения."""
        try:
            if self._relay:
                self._relay.all_off()
                self._relay.close()
                self._relay = None
        except Exception as e:
            self._log("WARN", f"Error closing relay: {e}")

        try:
            if self._tegam:
                self._tegam.close()
                self._tegam = None
        except Exception as e:
            self._log("WARN", f"Error closing Tegam: {e}")

        # Переводим индикаторы в 'unknown' после отключения
        self._ui_call(self.on_instrument_status, "tegam",   "unknown")
        self._ui_call(self.on_instrument_status, "arduino", "unknown")
        self._log("INFO", "Instruments disconnected")

    # ──────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ──────────────────────────────────────────────────────────────────────────

    def _switch_relay(self, cal_point: CalPoint) -> bool:
        """Переключить реле на нужную точку. Вернуть True если OK."""
        try:
            point_num = int(cal_point.relay[1])   # "R2" → 2
            return self._relay.select_point(point_num)
        except Exception as e:
            self._log("ERR", f"Relay switch error: {e}")
            return False

    def _compute_gum(self, cal_point: CalPoint,
                     readings_ohm: List[float]) -> PointResult:
        """
        GUM Type A: среднее, s(n-1), u=s/√n, U=2u (k=2, 95%).
        Возвращает заполненный PointResult.
        """
        import math
        n    = len(readings_ohm)
        mean = sum(readings_ohm) / n
        s    = math.sqrt(sum((x - mean) ** 2 for x in readings_ohm) / (n - 1))
        u    = s / math.sqrt(n)
        U    = 2 * u     # k=2, 95% confidence

        # Конвертируем в единицы отображения
        factor = self._display_factor(cal_point.display_unit)
        tol    = cal_point.tolerance_ohm()
        passed = cal_point.is_pass(mean)

        return PointResult(
            point_num     = cal_point.point,
            nominal_ohm   = cal_point.nominal_ohm,
            ref_value_ohm = cal_point.ref_value_ohm,
            readings      = readings_ohm,
            mean_ohm      = mean,
            u_expanded    = U,
            display_unit  = cal_point.display_unit,
            display_value = mean * factor,
            display_u     = U * factor,
            tolerance_ohm = tol,
            passed        = passed,
        )

    def _to_display(self, ohm: float, unit: str) -> float:
        """Перевести значение из Ом в единицы отображения."""
        return ohm * self._display_factor(unit)

    @staticmethod
    def _display_factor(unit: str) -> float:
        """Коэффициент перевода Ом → единица отображения."""
        return {"mOhm": 1e3, "Ohm": 1.0, "KOhm": 1e-3, "MOhm": 1e-6}.get(unit, 1.0)

    @staticmethod
    def _decimals(unit: str) -> int:
        """Количество знаков после запятой для данной единицы."""
        return {"mOhm": 1, "Ohm": 3, "KOhm": 4, "MOhm": 4}.get(unit, 3)

    def _sleep_with_abort(self, seconds: float):
        """Ждать seconds секунд, но прерваться если пришёл сигнал abort."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._abort.is_set():
                return
            time.sleep(0.05)

    def _set_state(self, new_state: State):
        """Установить новое состояние и уведомить UI."""
        with self._lock:
            self._state = new_state
        self._ui_call(self.on_state_change, new_state)

    def _log(self, level: str, message: str):
        """Написать в лог (через колбэк → UI)."""
        print(f"[SESSION][{level}] {message}")   # дублируем в консоль
        self._ui_call(self.on_log, level, message)

    def _error(self, message: str):
        """Критическая ошибка: логируем, уведомляем UI, переходим в ABORTED."""
        self._log("ERR", message)
        self._set_state(State.ABORTED)
        self._ui_call(self.on_error, message)

    def _ui_call(self, func: Callable, *args):
        """
        Безопасно вызвать функцию в главном потоке UI.
        Если ui_root установлен — используем root.after(0, ...).
        Если нет (тест без UI) — вызываем напрямую.
        """
        if self.ui_root is not None:
            # after(0, ...) — поставить в очередь событий tkinter
            self.ui_root.after(0, func, *args)
        else:
            try:
                func(*args)
            except Exception as e:
                print(f"[SESSION] Callback error: {e}")

    def finish_session(self):
        """Вызвать после сохранения отчёта — вернуть в IDLE."""
        self._set_state(State.IDLE)
        self._log("INFO", "Session closed")


# _MockRelay удалён.
# Arduino подключается всегда — USE_MOCK влияет только на Tegam (RS-232).
