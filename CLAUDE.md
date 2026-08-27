# Desk-Mixer

A desk-top two-deck music mixer. A physical device — dials, buttons, LCD — built on a **Teensy 4.1**
on a custom PCB, plus a **Python companion app** that loads music onto it from a laptop.

## Repository map

| Path | What | Read before working here |
|---|---|---|
| `Firmware/` | Teensy 4.1 firmware (PlatformIO, C++) — **Ryan writes this** | `Firmware/CLAUDE.md` |
| `App/` | Laptop companion app (Python + PySide6) | `App/CLAUDE.md` |
| `Electrical/` | KiCad schematics + board — **Ryan owns this** | `Electrical/CLAUDE.md` |
| `Docs/` | Engineering source of truth — pinout, protocol, ADRs | — |
| `Tools/` | Cross-project code generation | — |
| `.claude/skills/` | Project skills (see `Docs/claude-setup-guide.md`) | — |

**Each sub-project has its own `CLAUDE.md` with rules specific to it.** This file holds only what is
true across all three. When working inside a sub-project, its `CLAUDE.md` applies on top of this one.

## Hard facts — do not re-derive or re-litigate these

These were established by reading datasheets, the Teensy core sources, and the installed toolchain.
They are settled. If something here looks wrong, say so and cite evidence — do not silently assume.

- **Audio on the SD card is WAV**, 16-bit 44.1 kHz stereo. Not MP3. The laptop app transcodes before
  transfer. This keeps all Teensy CPU for DSP and makes seeking sample-accurate. See ADR 0002.
- **Two independent USB buses**, and they are not interchangeable:
  - *Device* — the Teensy's micro-USB, reached on the PCB by pogo pins to the **bottom-side D+/D−
    test pads**. Carries 5 V power, flashing, and the laptop-app data link.
    ⚠️ The micro-B receptacle and those pads are the **same electrical node** — only one may be
    connected at a time.
  - *Host* — the 5-pin header. Intended for USB-C audio out.
- **USB audio out does not work and no code should pretend otherwise.** `USBHost_t36` has no USB
  Audio Class driver, none exists for Teensy, and the host stack's isochronous support is unreliable.
  The output router exposes it as a sink that returns `OUTPUT_UNAVAILABLE`. See ADR 0005.
- **Device USB type is `USB_MIDI_SERIAL`** — compile-time, one per binary. Serial carries the app
  protocol; MIDI lets the mixer act as a Mixxx/Traktor control surface. MTP and USB Audio cannot
  coexist in any stock Teensy descriptor. See ADR 0001.
- **Audio deadline is 2.9 ms** — 128 samples at 44.1 kHz, 344 Hz. Everything in the audio path is
  bounded by this.
- **Spotify is used for playlist metadata only.** Track audio comes from a pluggable resolver. Do not
  add code that downloads audio from Spotify — it breaches their Terms. See ADR 0004.
- The **BM83 must be switched from Embedded Mode to Host Mode** with Microchip's Config Tool before
  any UART control works. This is a hardware provisioning step, not something firmware can do.

## Conventions across all sub-projects

- **Documentation is part of the change, not a follow-up.** A new subsystem lands with its docs.
- `Docs/` holds anything that must version with the code — pinout, wire protocol, audio graph, ADRs.
  Design thinking, component selection and to-dos live in Ryan's Obsidian vault, which points here:
  `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/100 VAULT/100 PROJECTS/Mini Desk Mixer/`.
  When writing notes there, match the existing style: **no YAML frontmatter, no tags, no callouts**
  (plain `>` blockquotes are used as one-line captions), `###` as the workhorse heading with `##`
  skipped, bold part numbers in tables, untagged code fences, and `DM <Topic>.md` file naming
  linked from `### Development` in the hub note.
- **Never hand-edit generated files.** `Tools/protocol.yaml` is the single source of truth for the
  device wire protocol; both the C header and the Python module are generated from it.
- Architecture decisions get an ADR in `Docs/decisions/`. Short: context, decision, consequences.
- Do not commit or push unless asked.

## Commands

```sh
# firmware
cd Firmware && pio run -e teensy41      # build
pio test -e native                                # host unit tests (once suites exist)
# app
cd App && pytest                       # tests
# cross-project
python Tools/generate_protocol.py --check         # protocol drift check
```
