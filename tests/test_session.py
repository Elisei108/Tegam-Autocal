"""
tests/test_session.py — тест CalibrationSession без UI.

Запуск из корня проекта:
    python tests/test_session.py

Использует USE_MOCK=True (реальные приборы не нужны).
Проверяет полный сценарий: AS FOUND → AS LEFT → REPORT.
"""

import sys
import os
import time

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calibration.session import CalibrationSession, State, PointResult

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "config", "config.xlsx")

# ── Счётчики для проверки что все колбэки вызвались ──────────────────────────
callbacks_fired = {
    "state_changes":  [],
    "measurements":   [],
    "points_done":    [],
    "phases_done":    [],
    "errors":         [],
    "log_entries":    [],
}


def on_state_change(state: State):
    callbacks_fired["state_changes"].append(state)
    print(f"\n  >>> STATE: {state.name}")


def on_measurement(pt_idx: int, meas_idx: int, value: float, unit: str):
    callbacks_fired["measurements"].append((pt_idx, meas_idx, value, unit))


def on_point_done(pt_idx: int, result: PointResult):
    callbacks_fired["points_done"].append(result)
    status = "PASS" if result.passed else "FAIL"
    dec = {"Ohm": 3, "KOhm": 4, "MOhm": 4, "mOhm": 1}.get(result.display_unit, 3)
    print(f"  → Point {result.point_num} {status}: "
          f"{result.display_value:.{dec}f} {result.display_unit} "
          f"± {result.display_u:.{dec}f}  "
          f"(tol ±{result.tolerance_ohm:.6f} Ohm)")


def on_phase_done(phase: str, results):
    callbacks_fired["phases_done"].append(phase)
    passed = sum(1 for r in results if r.passed)
    print(f"\n  ═══ {phase} complete: {passed}/{len(results)} PASS ═══")


def on_error(msg: str):
    callbacks_fired["errors"].append(msg)
    print(f"\n  !!! ERROR: {msg}")


def on_log(level: str, message: str):
    callbacks_fired["log_entries"].append((level, message))
    # Выводим только не-INFO чтобы не засорять вывод
    if level not in ("INFO",):
        print(f"  [{level}] {message}")


# ── Запуск теста ──────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("TegamCAL — CalibrationSession test (no UI, USE_MOCK=True)")
    print("=" * 60)

    session = CalibrationSession()
    session.on_state_change = on_state_change
    session.on_measurement  = on_measurement
    session.on_point_done   = on_point_done
    session.on_phase_done   = on_phase_done
    session.on_error        = on_error
    session.on_log          = on_log

    # Запускаем сессию
    session.start_session(
        operator    = "Test Operator",
        serial_no   = "TG-001234",
        temperature = "23.2",
        humidity    = "48",
        config_path = CONFIG_PATH,
    )

    # Ждём пока сессия дойдёт до REPORT или ABORTED (макс. 60 сек)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if session.state in (State.REPORT, State.ABORTED, State.ADJUST):
            break
        time.sleep(0.2)

    # Если дошли до ADJUST — подтверждаем (симулируем нажатие оператора)
    if session.state == State.ADJUST:
        print("\n  [TEST] Simulating operator ADJUST confirmation...")
        time.sleep(1.0)
        session.confirm_adjust()
        # Ждём дальше
        while time.monotonic() < deadline:
            if session.state in (State.REPORT, State.ABORTED):
                break
            time.sleep(0.2)

    # ── Итоги ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    sd = session.session_data
    print(f"  Operator:     {sd.operator}")
    print(f"  Serial No:    {sd.serial_no}")
    print(f"  Started:      {sd.started_at}")
    print(f"  Finished:     {sd.finished_at}")
    print(f"  Adjust done:  {sd.adjust_done}")
    print(f"  Final state:  {session.state.name}")

    print(f"\n  State changes:  {[s.name for s in callbacks_fired['state_changes']]}")
    print(f"  Measurements:   {len(callbacks_fired['measurements'])} total")
    print(f"  Points done:    {len(callbacks_fired['points_done'])}")
    print(f"  Phases done:    {callbacks_fired['phases_done']}")
    print(f"  Errors:         {callbacks_fired['errors']}")

    # Проверяем ожидаемые условия
    errors = []
    if len(callbacks_fired["measurements"]) < 8:
        errors.append("Too few measurements fired")
    if len(callbacks_fired["points_done"]) < 4:
        errors.append("Not all points_done callbacks fired")
    if "AS FOUND" not in callbacks_fired["phases_done"]:
        errors.append("on_phase_done('AS FOUND') never called")
    if "AS LEFT" not in callbacks_fired["phases_done"]:
        errors.append("on_phase_done('AS LEFT') never called")
    if callbacks_fired["errors"]:
        errors.append(f"Unexpected errors: {callbacks_fired['errors']}")
    if session.state not in (State.REPORT, State.IDLE):
        errors.append(f"Unexpected final state: {session.state.name}")

    print()
    if errors:
        print("  ✗ FAILED:")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)
    else:
        print("  ✓ ALL CHECKS PASSED")
        session.finish_session()
        print("  Session closed → IDLE")

    print("=" * 60)


if __name__ == "__main__":
    run()
