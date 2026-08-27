# Desk-Mixer — Teensy 4.1 Firmware

Two-deck audio playback, mixing and control-surface handling.

**Status: scaffolding only.** `src/main.cpp` holds a bare superloop and nothing else. The module
breakdown is deliberately undecided — hardware is not finalised, and the structure should follow
the hardware rather than lead it. This README is the integration reference to build against.

---

## Build

```sh
pio run -e teensy41            # build
pio run -e teensy41 -t upload  # flash
pio device monitor             # serial console
pio test -e native             # host unit tests (once suites exist)
```

Current footprint: ~9.5 kB flash, of 7.75 MB. Effectively all of it is still free.

---

## Hardware

| Function | Part | Interface |
|---|---|---|
| MCU | **Teensy 4.1** (i.MX RT1062, 600 MHz Cortex-M7) | — |
| Audio codec | **SGTL5000** | I2S1 + I²C `0x0A` |
| Bluetooth audio | **BM83SM1-00TA** | I2S2 (audio) + UART (control) |
| Storage | microSD | native 4-bit SDIO (`BUILTIN_SDCARD`) |
| Display | SPI panel, **not yet selected** | SPI |
| Host link | USB CDC serial | Teensy device port |

### Clock and data pins — fixed by the silicon

| Bus | MCLK | BCLK | LRCLK | TX | RX |
|---|---|---|---|---|---|
| I2S1 (SAI1) → SGTL5000 | 23 | 21 | 20 | **7** | **8** |
| I2S2 (SAI2) → BM83 | 33 | 4 | 3 | 2 | 5 |

SAI1 and SAI2 are independent peripherals, so **both run at once**. The analog jack and Bluetooth
are fed from separate buses, and Bluetooth gets a digital feed with no analog round trip.

S/PDIF is available on pin 14 and currently unused. Full map: [`Docs/pinout.md`](../Docs/pinout.md).

### USB

- **Device** — the micro-USB port, reached on the PCB via pogo pins to the bottom-side D+/D− test
  pads when the Teensy is seated in its header. Power and data both come from the panel USB-C, so
  the Teensy sees one host and one supply — no pads or traces need cutting, and the board can still
  be flashed standalone through its own micro-USB when removed.
  ⚠️ The receptacle and those pads are the **same electrical node**, so **never connect the panel
  port and the micro-USB at the same time** — that ties two hosts' VBUS together.
- **Host** — the 5-pin header, wired to a USB-C connector for audio out. **There is no USB Audio
  Class host driver for Teensy**, so this path has no software route today. See
  [ADR 0005](../Docs/decisions/0005-usb-host-audio.md).

---

## The superloop

`main.cpp` runs fixed-cadence tasks against `millis()`:

```c
if ((now - s_last_control_ms) >= CONTROL_PERIOD_MS) {
    s_last_control_ms = now;
    control_task();
}
```

Chosen over an RTOS because the Teensy audio library already preempts from an interrupt, so the
loop's only job is to run each task often enough. Fixed cadences make every task's worst-case
latency obvious by reading the file — no priority inversion, no stack sizing, no scheduler to
reason about.

**The one rule: nothing in the loop may block.** No `delay()`, no busy-wait, no spin on a peripheral
flag. A task that needs to wait returns and resumes on the next tick.

### Adding a task

Add a period macro, a `s_last_*_ms` timestamp, and a branch. Keep the cadence honest: a task that
runs every 1 ms must actually complete in well under 1 ms.

Starting cadences, adjust once there is something to measure:

| Task | Period | Why |
|---|---|---|
| control surface | 1 ms | responsiveness — this is what makes the device feel tight |
| host link / UARTs | 2 ms | drain buffers before they overflow, but do not starve controls |
| display | 30 ms | ~33 fps; SPI refresh is expensive and the eye is not |

### When the superloop stops being enough

Watch for: a task that cannot complete inside its cadence, or work that must happen at a precise
time rather than "soon". The usual escalations, roughly in order of cost:

1. **Split the long task** across ticks with a small state machine. Cheapest, and usually enough.
2. **Move it to an interrupt** — `IntervalTimer` for periodic work, or a peripheral ISR.
3. **Use DMA** for bulk transfers, so the CPU is not the bottleneck.
4. **Adopt an RTOS** (`TeensyThreads` or FreeRTOS). Only worth it if several tasks genuinely need
   independent blocking; it brings stack sizing and priority questions the superloop avoids.

The audio engine is already effectively option 2 — it runs from the SAI interrupt regardless.

---

## Integration notes

Reference material for each subsystem. **None of this is implemented.**

### Audio — the 2.9 ms deadline

128 samples at 44.1 kHz means one block every **2.9 ms**, 344 times a second. Every audio object's
`update()` runs inside that window at interrupt priority. Overrunning it does not slow the device
down; it drops audio.

Inside any audio callback: **no heap, no blocking, no `Serial`, no unbounded loops.**

The Teensy Audio Library builds a static graph of `AudioStream` objects wired by `AudioConnection`
objects at file scope. A two-deck mixer shape:

```
player A ─► filter ─┐
                    ├─► mixer L/R ─┬─► AudioOutputI2S  ─► SGTL5000 ─► jack
player B ─► filter ─┘              └─► AudioOutputI2S2 ─► BM83 ─► Bluetooth
```

Practical notes:

- `AudioMemory(n)` allocates the block pool. Start around 60 and tune against
  `AudioMemoryUsageMax()`; if usage reaches the allocation, blocks are being starved.
- `AudioProcessorUsageMax()` gives peak CPU as a percentage. Keep it well under ~70 % so transients
  have headroom.
- `AudioConnection` objects exist purely for their constructor side effect. cppcheck reads them as
  unused, which is why `unusedVariable` is suppressed in `.cppcheck-suppressions`.
- Both I2S outputs can be fed permanently. Muting a sink on output switch causes a click; leaving
  both connected and changing only what the UI calls "active" avoids it.

**Varispeed.** The stock library has no variable-rate SD player. `AudioPlaySdResmp` from
[`teensy-variable-playback`](https://github.com/newdigate/teensy-variable-playback) resamples on the
fly — pitch and tempo move together, like a turntable. Its transport API is narrower than it looks
and is worth reading before designing around it:

- `playWav(path)` is the **only** way to start, and always begins at the configured play-start point
- `stop()` clears the playing flag but **does not rewind**
- there is **no `play()`** and no seek

So resume has to be expressed as *set the play-start point, then re-open*, where `setPlayStart`
takes **frames** (per-channel samples), not bytes or milliseconds:

```c
uint32_t frames = (uint32_t)(((uint64_t)position_ms * 44100u) / 1000u);
player.setPlayStart(play_start_arbitrary, frames);
player.playWav(path);
```

Key-lock (WSOLA time-stretch) costs roughly half a core when active — probably a v2 question.

### SGTL5000

`AudioControlSGTL5000` from the stock library. I²C address `0x0A` by default, `0x2A` if the address
pin is pulled high. `enable()` must succeed before audio flows; treat failure as "no analog output"
rather than a fatal error. `volume()` drives the headphone amp, `lineOutLevel()` the line output.

The codec needs its analog supply and charge-pump capacitors in place before it will respond — NXP
**AN3663** is the reference layout.

### BM83 Bluetooth

The device **transmits** to Bluetooth headphones — the A2DP **source** role. Use the
**`BM83SM1-00TA`**, which ships with Microchip's Audio Transceiver firmware and supports source.
The `BM83SM1-00AB` is the Wireless Concert Technology variant for speaker-to-speaker linking and is
the wrong part here.

The TX encoder is **SBC** at 44.1/48 kHz, so the Bluetooth path is capped at SBC quality regardless
of what is on the card.

**The Teensy is the I2S master; the BM83 is the slave.** MCLK is mandatory in slave mode — the
module is strict about clock synchronisation, and `AudioOutputI2S2` drives it on pin 33.

| Signal | Teensy | BM83 |
|---|---|---|
| BCLK | 21 | `SCLK1` (3) |
| LRCLK | 20 | `RFS1` (2) |
| Audio data out | 2 | `DT1` (4) |
| MCLK | 33 | `MCLK1` (5) |
| UART out | 1 (`TX1`) | `HCI_RXD` (13) |
| UART in | 0 (`RX1`) | `HCI_TXD` (12) |
| Reset | *TBD* | `RST_N` (43) |
| Wake | *TBD* | `MFB` (26) |
| Boot mode | *TBD* | `P3_4` (31) |

⚠️ **Three of those GPIOs are unallocated**, and nothing works without them. `MFB` must go **high
2–3 ms before every UART command** to wake the module from power save; `BM83_EN` is a supply enable
and does not cover it. `RST_N` and `P3_4` are what make in-system flashing possible.

### Provisioning and the serial relay

A fresh `-00TA` already has the right firmware, so what it needs is a **configuration** write:
Host Mode, I2S role **Slave**, I2S path **Input**. Without that the UART does not answer and the
module may try to drive the I2S clocks itself.

Flashing is done by a **PC**, over the module's UART — but it can go **through the Teensy**, which
is the chosen route and needs no extra connector or USB traces to the module:

1. Teensy drives `P3_4` low and pulses `RST_N` → module enters test/flash mode.
2. Teensy runs a transparent serial relay: USB `Serial` ↔ `Serial1`.
3. On the PC, `isUpdate` or the Config GUI Tool selects the **Teensy's COM port**, transport UART.
4. Teensy drives `P3_4` high and resets → app mode.

**The relay is a firmware deliverable.** Small, but it must be transparent about baud and must not
buffer or reorder in a way the tool's timing notices.

An unprovisioned module is silent and gives no diagnostic, so the failure looks exactly like a
wiring fault. Proving the chain on an EVB first separates "not configured" from "wired wrong".

**Antenna keep-out:** no copper, traces or components beneath the module's PCB antenna.

**No Arduino or Teensy library exists**, so the driver is ours. Packet format is in Microchip
**DS50002896A** (*BM83 Host MCU Firmware Development Guide*); reference source, written for PIC32,
is at [`MicrochipTech/bm83_getting_started`](https://github.com/MicrochipTech/bm83_getting_started).

Framing, from that document:

```
[0]    0xAA start byte
[1..2] payload length, BIG-endian, counting opcode + parameters
[3]    opcode
[4..]  parameters
[n]    checksum: two's complement of the sum of every byte after the start byte
```

A well-formed packet's bytes after the start byte sum to zero modulo 256 — that is the property to
verify against. Note the length is **big-endian and counts the opcode**, the opposite of the host
link protocol below; do not copy one codec into the other.

Bluetooth adds 150–300 ms of latency. The wired jack is the monitoring output for beat-matching;
Bluetooth is an audience output, and its metering should not be presented as real-time.

### SD card

Built-in socket on native **4-bit SDIO** via `SD.begin(BUILTIN_SDCARD)` — not SPI, and much faster.
Teensyduino ships `SD 2.0.0` as a wrapper over `SdFat 2.1.2`; drop to `SdFat` directly if you need
its faster APIs or exFAT specifics.

**Audio streams; nothing is loaded whole.** A 4-minute WAV is ~42 MB against 1 MB of RAM, so the
player refills a small buffer from the card while the audio interrupt drains 128 samples every
2.9 ms.

| | |
|---|---|
| One stereo deck | 176.4 kB/s |
| Two decks | **352.8 kB/s** |
| SDIO capability | many MB/s |

So throughput was never the risk — **latency spikes** are. A 32 kB buffer per deck is ~186 ms of
cushion, which is ample against SD read jitter. `AudioPlaySdResmp` buffers more than the stock
player because resampling needs lookahead, and can move that buffer to PSRAM if it is ever needed.

**Never write to the card while playing.** Card write bursts stall reads, and that is the classic
dropout cause. Transfers are rare — a few times a year — so this costs nothing. Make it a hard
interlock in firmware: refuse `FILE_BEGIN` unless both decks are stopped, rather than trusting the
app to behave.

Teensy 4.1 has pads for **8 MB PSRAM**, which can be added later if buffering ever needs it.

Card layout and the WAV-only decision: [`Docs/sd-layout.md`](../Docs/sd-layout.md),
[ADR 0002](../Docs/decisions/0002-wav-not-mp3.md).

### Display

Panel not chosen. Worth keeping the drawing calls behind a small surface of your own so the concrete
driver can be swapped without touching UI logic — the panel decision and the menu logic are
independent problems.

The `DISP_*` nets are already assigned (see the pinout). SPI refresh is slow relative to everything
else, so buffer draws and push once per display tick rather than writing through.

### Control surface

Teensy 4.1 has 18 ADC-capable pins, enough for the full fader/knob budget with no multiplexer.
Encoders belong on the **hardware quadrature timer pins**, where decoding costs zero CPU.

Two things worth handling early, because they are invisible until they annoy you: cheap pots dither
by a couple of counts, so a small hysteresis stops the audio engine being told to change gain every
tick; and pots rarely reach their electrical extremes, so an end deadzone is what makes a closed
fader actually silent.

`Interface.kicad_sch` is still empty, so the pin allocation is provisional.

**Jack insertion is detectable.** `J3` is an `SJ1-3525N`, the tip-and-ring switch variant — the
switches are normally closed to their contacts and open when a plug is inserted. Because the switch
shorts to the audio tip, a plain pull-up reads high in both states; see `Docs/pinout.md` for a
divider that works. Currently unwired and unallocated.

### Host link

USB type is **`USB_MIDI_SERIAL`**, set in `platformio.ini`. That gives a CDC serial port for the
companion app plus a MIDI device, so the mixer can double as a control surface for Mixxx or Traktor.

USB type is compile-time and exclusive — MTP and USB Audio cannot be added to this combination. See
[ADR 0001](../Docs/decisions/0001-usb-port-roles.md).

The wire protocol is specified in [`Docs/protocol.md`](../Docs/protocol.md) and generated from
`Tools/protocol.toml`. The app side is implemented and tested; **the firmware side is not written**.
Generation into the firmware tree is currently switched off — set `H_OUT` in
`Tools/generate_protocol.py` to wherever the header should live to turn it back on.

---

## Structure

`include/` mirrors `src/`, and there is no `lib/` folder. Beyond that the breakdown is open.

One suggestion worth weighing as modules appear: keep the parts that make *decisions* separate from
the parts that touch *hardware*. A file that includes no Arduino or Teensy headers can be compiled
and unit-tested on the laptop, which matters here because of the next section. Framing, checksums,
gain curves, menu logic and format parsing all tend to fall out this way naturally.

To wire a file into host testing, list it in `[pure] sources` in `platformio.ini`.

---

## Testing

| Tier | Command | Covers |
|---|---|---|
| Host unit | `pio test -e native` | anything with no hardware includes |
| On-target | `pio test -e teensy41_test` | SD, I²C, UART, timing |
| Static | `cppcheck` (see `.cppcheck-suppressions`) | whole tree |
| Style | `python3 ../Tools/check_style.py` | house style, mechanically |

**There is no Teensy 4.1 emulator.** No Renode or QEMU machine model exists for the i.MX RT1062,
and the peripherals that matter (SAI/I2S, SDIO) are not modelled anywhere. Host tests over
hardware-independent code, plus fakes for the rest, are the only automated option — which is the
main argument for the split suggested above.

**On-target caveat:** PlatformIO claims the first `Serial` as its test transport, so all `Serial`
use must sit inside `#ifndef UNIT_TEST`. Teensy 4.1 on-target runs are also known to stall after
upload occasionally, so that tier is a local gate, not a CI gate.

CI skips the host-test job while `test/` is empty and picks it up automatically once a suite lands.

---

## Documentation

```sh
doxygen Doxyfile && open doxygen/html/index.html
```

Doxygen emits a "member belongs to two different groups" warning for `main.cpp` — a consequence of
the house style's blank `@name` opening an anonymous member group. Cosmetic.
