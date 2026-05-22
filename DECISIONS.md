# Project Decisions Log — TegamCAL

## 2026-05-02

### Architecture
- Project structure: modular — separate files for ui, instruments, database, reports
- Instrument abstraction: USE_MOCK flag in config.py
- Stage 1: Arduino Nano + 4-relay board (2-wire, demo only)
- Stage 2: Keithley 2750 switcher (4-wire Kelvin connection)

### Measurements
- 5 readings per calibration point
- GUM Type A uncertainty calculation:
  - mean = average of 5 readings
  - s = standard deviation (n-1)
  - u = s / sqrt(n)
  - U = 2 * u (k=2, 95% confidence)
- Report format: 10.032 Ohm ± 0.004 Ohm (k=2, 95%)

### Calibration Process
- AS FOUND run before calibration (automatic)
- Calibration: semi-automatic (operator presses ENTER on Tegam panel)
- AS LEFT run after calibration (automatic)
- Calibration triggered only if any point FAIL

### Configuration
- calibration_config file in project folder
- Contains: reference standards, tolerances, relay mapping
- Updated once per year after reference recalibration
- TODO: create config file when reference data is available

### Standards & Compliance
- Foundation: ISO/IEC 17025:2017
- Defense/Aerospace: AS9100 Rev D
- Automotive: IATF 16949
- Medical/Pharma: ISO 13485 + 21 CFR Part 11
- Full compliance roadmap: see COMPLIANCE_ROADMAP.md
- Stage 1: no compliance requirements (prototype/demo)

### UI
- Language: English (Stage 1 and 2)
- Code comments: Russian (Stage 1), English (Stage 2)
- Framework: tkinter

### Database
- Stage 1: SQLite local
- Stage 2: SQL server via enterprise WiFi

### Reports
- Stage 1: local PDF + Excel
- Stage 2: network folders + server database

### Known Limitations (Stage 1)
- 2-wire connection adds lead resistance error
- Must be noted in all Stage 1 reports: "Demo only — 2-wire connection"
