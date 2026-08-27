# Desk-Mixer — PCB

KiCad 10 project (`Desk-DJ`). **Four-layer**, 1.6 mm FR4.

> **This directory is hand-edited in KiCad.** Nothing else in this repository modifies it, and
> tooling should not either — editing `.kicad_sch` or `.kicad_pcb` as text corrupts UUIDs and net
> linkage.

## Sheets

| Sheet | State |
|---|---|
| `USB_Input.kicad_sch` | USB-C power input: `USBLC6-2SC6` ESD → `TUSB320` CC → eFuse |
| `Power.kicad_sch` | `TPS259251` eFuse → `TPSM82903` buck → +3V3. Most complete sheet |
| `Microcontrollers.kicad_sch` | Teensy 4.1 pin budget assigned; BM83 placed but unwired |
| `Audio_IO.kicad_sch` | SGTL5000 I2S/I²C/headphone out, `SJ1-3525N` jack. No power section yet |
| `LCD.kicad_sch` | **empty** |
| `Interface.kicad_sch` | **empty** |

The board has 36 footprints imported and **no tracks, pours or outline**.

Four layers rather than two: the stackup has to give an uninterrupted ground plane under the USB
differential pairs and both I2S MCLK lines. Those are 11.29 MHz square waves running near the
analog section, and on two layers you end up choosing which of impedance control or analog
isolation to compromise.

## What firmware depends on

The pin map lives in [`Docs/pinout.md`](../Docs/pinout.md) and
`Firmware/include/config.h`, both derived from this schematic.

**If they disagree with the schematic, the schematic wins.** Flag the discrepancy rather than
editing either side silently.

## BM83 — what the board must provide

Use **`BM83SM1-00TA`** (Audio Transceiver firmware, A2DP source), not `-00AB` (speaker linking).

Beyond I2S2 and the UART, three control lines need Teensy GPIOs: `MFB` (26), `RST_N` (43) and
`P3_4` (31). `P3_4` and `RST_N` are what let the Teensy put the module into flash mode and act as a
serial relay for Microchip's PC tools — which is how a soldered module stays recoverable without a
programming header or USB traces to the module.

No copper, traces or components beneath the module's PCB antenna.

## Open items

A read of the netlist on 2026-08-26 turned up several things worth checking next time this is
open — an I²C net-name mismatch, a power-button symbol that is actually an LDO, the SGTL5000's
missing power section, and the unwired BM83 among them. They are recorded in
[ADR 0006](../Docs/decisions/0006-electrical-review.md) as reference, not as a task list.

## Portability warning

Every non-stock symbol and footprint resolves through the **global** KiCad library table at
`~/Local/System-Local/Packages/KiCad/…`, outside this repository. Cloning the repo on another
machine will break all of them. Vendoring the project libraries under this directory would fix it.

## Ignored files

`.gitignore` excludes KiCad's per-user state: `*.kicad_prl`, `fp-info-cache`, `*-backups/`,
`_restore_backup_*/`, lock files, and `.history/`. That last one is KiCad 10's Local History,
which keeps its **own nested git repository** — it was previously picked up as a gitlink with no
`.gitmodules`, which breaks `git submodule status`.
