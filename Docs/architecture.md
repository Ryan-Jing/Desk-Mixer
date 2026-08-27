# System architecture

## What the device is

A desk-top two-deck music mixer. Two tracks play at once; physical faders, knobs and buttons let
you crossfade, filter and vary the tempo of each. An LCD shows what is loaded. A laptop app puts
music on it.

## The three pieces

```
┌────────────────────────┐        USB CDC serial         ┌──────────────────────────┐
│  App        │◄─────────────────────────────►│  Firmware       │
│  Python + PySide6      │   custom protocol, ADR 0001   │  Teensy 4.1 firmware     │
│                        │                               │                          │
│  Spotify ─► metadata   │                               │  2 decks, mixer, DSP     │
│  Resolver ─► audio file│                               │  LCD, control surface    │
│  ffmpeg ─► WAV         │                               │  BM83 Bluetooth driver   │
└────────────────────────┘                               └──────────────────────────┘
                                                                      │
                                                         ┌────────────┴────────────┐
                                                         │   PCB        │
                                                         │   KiCad, Ryan's domain  │
                                                         └─────────────────────────┘
```

## Data flow — getting music onto the device

```
Spotify playlist          (metadata only — titles, artists, ISRC; ADR 0004)
      │
      ▼
TrackResolver             (local music library by default; pluggable)
      │  local audio file
      ▼
ffmpeg transcode          16-bit 44.1 kHz stereo WAV (ADR 0002)
      │
      ▼
USB serial transfer       FILE_BEGIN → FILE_CHUNK ×N → FILE_END, CRC-32 verified
      │
      ▼
SD card  /library/<playlist>/<track>.wav
```

Spotify is never asked for audio. That split is a deliberate constraint, not an implementation
gap — see [ADR 0004](decisions/0004-track-resolver.md).

## Data flow — playing

```
SD card ──► AudioPlaySdResmp ×2 ──► filters ──► mixer ──┬──► SGTL5000 ──► 3.5 mm jack
            (varispeed resampling)                      ├──► BM83 (I2S2) ──► Bluetooth
                                                        └──► USB host ──► ✗ no driver (ADR 0005)
```

Two independent I2S peripherals mean the analog and Bluetooth paths run **simultaneously** from
separate buses, and Bluetooth is fed digitally with no analog round trip.

Details in [audio-architecture.md](audio-architecture.md).

## Firmware structure

**Not yet decided.** `src/main.cpp` holds a bare superloop; the module breakdown will follow the
hardware rather than lead it. `include/` mirrors `src/` and there is no `lib/` folder — beyond that
the layout is open.

One structural idea carries real weight, because there is **no Teensy 4.1 emulator**: code that
includes no Arduino or Teensy headers can be compiled and unit-tested on the laptop. Separating the
parts that make *decisions* from the parts that touch *hardware* is what makes any automated
firmware testing possible at all. Framing, checksums, gain curves, menu logic and format parsing
tend to fall out that way naturally. See [testing.md](testing.md).

Integration notes for each subsystem — audio graph, BM83 framing, SD, controls — are in
[`Firmware/README.md`](../Firmware/README.md).

## Timing

Audio runs at interrupt priority on a **2.9 ms deadline** (128 samples @ 44.1 kHz). Everything
else is a cooperative superloop in `main.cpp`:

| Task | Period |
|---|---|
| control surface | 1 ms |
| host link + BM83 UART | 2 ms |
| display | 30 ms |

No RTOS. The audio engine already preempts, and fixed cadences make each task's worst-case latency
obvious by inspection.

## Where things are written down

| Question | Answer lives in |
|---|---|
| Which pin does X use? | [pinout.md](pinout.md) |
| How does the audio graph work? | [audio-architecture.md](audio-architecture.md) |
| What does the app send the device? | [protocol.md](protocol.md) |
| What is on the SD card? | [sd-layout.md](sd-layout.md) |
| How do I test this? | [testing.md](testing.md) |
| Why is it done that way? | the ADRs, starting at [0001](decisions/0001-usb-port-roles.md) |
| How do I configure Claude for this repo? | [claude-setup-guide.md](claude-setup-guide.md) |

Design thinking, component selection and to-dos live in the Obsidian vault, which points here.
Anything that must version with the code lives in this folder.
