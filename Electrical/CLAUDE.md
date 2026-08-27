# Desk-Mixer — PCB

KiCad 10 project (`Desk-DJ`). **Four-layer**, 1.6 mm FR4.

## Do not modify anything in this directory

The electrical design is Ryan's, worked on independently and directly in KiCad. **Never edit
`.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, `.kicad_prl`, or anything under `Desk-DJ-backups/`,
`.history/`, or `_restore_backup_*/`.** Editing KiCad files as text corrupts UUIDs and net linkage
in ways that are painful to unpick.

Reading them to answer questions is fine and often useful — netlists, pin assignments and component
values are all extractable with `grep`.

Component-selection questions get answered in conversation. If a change is needed, describe it and
let Ryan make it in KiCad.

## What firmware depends on

The authoritative pin map lives in `Docs/pinout.md`, derived from this schematic. If it disagrees
with the schematic, **the schematic wins** — flag the discrepancy rather than editing either side
silently.

## Known state (as of 2026-08-26, for reference)

Designed: USB-C power path (TUSB320 CC → TPS259251 eFuse → TPSM82903 buck → +3V3), Teensy pin
budget, partial SGTL5000 front-end.

Not yet designed: `LCD.kicad_sch` and `Interface.kicad_sch` are empty; the BM83 is placed with zero
nets; the SGTL5000 has no power section; the PCB has no tracks, pours or board outline.

Open pin allocations: `BM83_MFB`, `BM83_RST_N` and `BM83_P3_4` (all required — see ADR 0003), plus
the jack-detect line from `J3`. Pins 22, 36, 37, 40, 41 are free.

⚠️ Known schematic issues: the **I2S1 data lines are swapped at the Teensy** (pad 7 is `TX_DATA0`
but carries `I2S1_TEENSY_IN`), and pin 19 sits on `I2C_SDL` while the codec is on `I2C_SCL`. Both
in ADR 0006.

Open items found while reading the netlist are recorded in `Docs/decisions/0006-electrical-review.md`.
