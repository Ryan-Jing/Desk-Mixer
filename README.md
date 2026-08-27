# Desk-Mixer

A desk-top two-deck music mixer. Two tracks play at once; physical faders, knobs and buttons let
you crossfade, filter and vary the tempo of each while an LCD shows what is loaded. A companion
app on your laptop puts music on it.

Built on a **Teensy 4.1** on a custom PCB.

---

## Repository

| Path | What |
|---|---|
| [`Firmware/`](Firmware/) | Firmware — PlatformIO, C++ |
| [`App/`](App/) | Companion app — Python + PySide6 |
| [`Electrical/`](Electrical/) | Schematics and board — KiCad |
| [`Docs/`](Docs/) | Engineering source of truth |
| [`Tools/`](Tools/) | Cross-project code generation and checks |

## Hardware at a glance

| Function | Part |
|---|---|
| MCU | Teensy 4.1 — i.MX RT1062, 600 MHz Cortex-M7 |
| Audio codec | SGTL5000 → 3.5 mm jack, via I2S1 |
| Bluetooth audio | BM83SM1-00TA, fed digitally over I2S2 |
| Storage | microSD, native 4-bit SDIO |
| Power | USB-C → TUSB320 CC → TPS259251 eFuse → TPSM82903 buck |

Both I2S peripherals run at once, so the analog and Bluetooth outputs are independent and
Bluetooth needs no analog round trip.

## How music gets on it

```
Spotify playlist  ──►  metadata only (titles, artists, ISRC)
                            │
                    TrackResolver  ──►  a local audio file you own
                            │
                    ffmpeg  ──►  16-bit 44.1 kHz stereo WAV
                            │
                    USB serial  ──►  SD card  /library/<playlist>/<track>.wav
```

Spotify is never asked for audio — that is a deliberate boundary, not a gap.
See [ADR 0004](Docs/decisions/0004-track-resolver.md).

## Quick start

```sh
# firmware
cd Firmware
pio run -e teensy41            # build
pio test -e native             # host unit tests (once suites exist)

# companion app
cd ../App
python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check .         # tests and type checks once modules exist
```

Enable the shared pre-push gate once:

```sh
git config core.hooksPath .githooks
```

## Documentation

| Read this | For |
|---|---|
| [architecture.md](Docs/architecture.md) | how the three pieces fit together |
| [pinout.md](Docs/pinout.md) | the Teensy pin map — source of truth |
| [audio-architecture.md](Docs/audio-architecture.md) | the audio graph, timing and CPU budget |
| [protocol.md](Docs/protocol.md) | the app ↔ device wire protocol |
| [sd-layout.md](Docs/sd-layout.md) | what lives on the card |
| [testing.md](Docs/testing.md) | the test strategy, and what it deliberately does not cover |
| [decisions/](Docs/decisions/) | why things are the way they are |
| [claude-setup-guide.md](Docs/claude-setup-guide.md) | configuring Claude Code for this repo |

## Two things worth knowing up front

**USB audio out does not work.** The USB-C on the host header has no software path: `USBHost_t36`
has no USB Audio Class driver, none exists for Teensy, and the host stack's isochronous support is
unreliable. The firmware reports that output as unavailable rather than pretending.
[ADR 0005](Docs/decisions/0005-usb-host-audio.md) covers the alternatives.

**The BM83 must be switched to Host Mode** with Microchip's Config Tool before its UART responds
to anything. It ships in Embedded Mode. [ADR 0003](Docs/decisions/0003-bluetooth-bm83.md).

## Status

| Area | State |
|---|---|
| Firmware | **scaffolding only** — bare superloop in `main.cpp`, builds clean. Module breakdown deliberately undecided |
| Companion app | **scaffolding only** — design and build order in [`App/README.md`](App/README.md) |
| Wire protocol | **specified**, with generators for both sides written but parked until each side picks a layout |
| Display | **panel not yet chosen** |
| Control surface | provisional pin map; `Interface.kicad_sch` is empty |
| PCB | 36 footprints placed, **no routing yet** |

Firmware is written by Ryan, with the architecture worked out collaboratively — integration notes
per subsystem are in [`Firmware/README.md`](Firmware/README.md). The app is unbuilt; its design and
a step-by-step build order are in [`App/README.md`](App/README.md).
