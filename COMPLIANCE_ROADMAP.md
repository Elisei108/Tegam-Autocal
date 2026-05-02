# Compliance Roadmap — TegamCAL

## Status: planned — not implemented

## Applicable Standards by Industry

### All industries (foundation)
- ISO/IEC 17025:2017 — calibration laboratory competence
  Requirements: audit trail, measurement traceability, 
  uncertainty evaluation, record retention

### Defense & Aerospace
- AS9100 Rev D — aviation, space, defense QMS
  Requirements: product safety, configuration management,
  counterfeit parts prevention, on-time delivery tracking

### Automotive
- IATF 16949:2016 — automotive QMS
  Requirements: ISO 17025 accredited calibration mandatory,
  statistical process control (SPC), FMEA, PPAP

### Medical & Pharma
- ISO 13485:2016 — medical device QMS
- 21 CFR Part 11 (FDA) — electronic records & signatures
  Requirements: audit trail, electronic signatures,
  access control, data integrity

## Features to implement when required

### 1. Audit Trail
- Table audit_log: who / what / when / old value / new value
- Append-only — no edit or delete allowed

### 2. User Access Control
- Roles: operator / engineer / administrator
- Operator: run calibration only
- Engineer: change parameters, cannot delete records
- Administrator: full access

### 3. Electronic Signature
- Operator signs every calibration report with login + timestamp
- Stored in DB, cannot be modified

### 4. Measurement Traceability
- Every result linked to reference standard
- Reference standard: serial number + calibration date + 
  traceability to NIST / PTB / BIPM

### 5. Data Integrity
- Results locked after save — no editing
- Daily DB backup
- Checksum verification on reports

### 6. Uncertainty of Measurement
- ISO 17025 requires uncertainty value on every report
- Example: 10.032 Ohm ± 0.002 Ohm (k=2, 95%)

## Notes
- Prototype (Stage 1): none of the above required
- Production (Stage 2): implement based on customer requirements
- Priority order: ISO 17025 → AS9100 → ISO 13485 → IATF 16949
