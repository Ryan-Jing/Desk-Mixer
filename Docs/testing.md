# Testing

## The honest constraint first

**There is no Teensy 4.1 emulator.** No Renode or QEMU machine model exists for the i.MX RT1062,
and the peripherals that actually matter here — SAI/I2S, USDHC/SDIO, the audio engine's interrupt
timing — are not modelled anywhere. Do not go looking for an emulation tier; it does not exist.

Everything below is built around that fact. The strategy is to make as much of the firmware as
possible *not need hardware*, and to be explicit about the part that does.

## Tiers

| # | Tier | Command | Runs in CI |
|---|---|---|---|
| 1 | Firmware host unit tests | `pio test -e native` | when suites exist |
| 2 | App unit tests | `pytest` | when suites exist |
| 3 | Firmware build | `pio run -e teensy41` | yes |
| 4 | Static analysis + style | `cppcheck`, `ruff`, `mypy`, `check_style.py` | yes |
| 5 | Protocol spec | `python3 Tools/generate_protocol.py --check` | yes |
| 6 | On-target tests | `pio test -e teensy41_test` | **no** — needs hardware |

### Tier 1 — hardware-independent firmware code

**No firmware modules exist yet.** The recommendation, when they do: keep the parts that make
*decisions* in files with **no Arduino, Teensy or hardware headers** — only `<stdint.h>`,
`<stddef.h>`, `<string.h>`, `<math.h>`.

Those files can be compiled and run on the laptop, which is the only automated firmware testing
available here. Candidates that tend to fall out naturally:

```
framing and checksums     deterministic byte-in, byte-out
gain and fader curves     pure arithmetic with invariants worth asserting
format parsing            e.g. a WAV header, given a buffer
menu and selection logic  index maths, no drawing
input conditioning        debounce and scaling, given a caller-supplied clock
```

Listing such a file in `[pure] sources` in `platformio.ini` is what makes `[env:native]` compile it.
A file that is not listed is never host-tested and nobody notices.

The question to ask when adding logic: **can this be decided without touching hardware?** If yes,
it can be tested; if it is tangled with peripheral calls, it cannot.

### Tier 2 — the app

**Not built yet.** The app is scaffolding; `App/README.md` holds the design and the build order.

The rule to hold to when it is built: **no test may touch the network, a real serial port, or a
real ffmpeg binary.** That stays achievable if the layering holds — everything except `ui/` usable
headless. Three fakes carry most of it:

- a **loopback transport** standing in for the serial link, able to play a fake device that ACKs or
  NACKs, so the whole transfer flow runs with no hardware;
- building the **ffmpeg argument vector separately from running it**, so the invocation is asserted
  without invoking anything;
- **captured JSON payloads** through the Spotify mapping function.

### Tier 5 — cross-implementation agreement

Opcodes and constants come from `Tools/protocol.toml`, so they cannot drift once generation is
enabled. The framing has to be implemented once per language, and **neither side is written yet**.
When they are, both should assert the **same reference vectors**:

```
CRC16("123456789")                     == 0x29B1
encode(FILE_CHUNK, 01 02 03 04 05)     == a5 21 05 00 01 02 03 04 05 2a f6
encode(PING)                           == a5 01 00 00 ac fb
```

If either side drifts, a test fails rather than the link mysteriously breaking. While generation is
parked, `--check` still validates the spec — duplicate opcodes and malformed entries.

### Tier 6 — on-target

For what genuinely cannot be faked: SD throughput, I²C enumeration of the SGTL5000, the BM83 UART
handshake, and real audio CPU load.

Note the BM83 will not answer at all until it has been switched to Host Mode with Microchip's
Config Tool — a hardware provisioning step, not a firmware bug.

Two caveats:

- **PlatformIO claims the first `Serial` as its test transport**, so every `Serial` use in the
  firmware must sit inside `#ifndef UNIT_TEST`.
- Teensy 4.1 on-target runs are known to stall after upload occasionally. This tier is a **local
  gate, not a CI gate**.

## What is not covered, and is known not to be

Stated plainly so nobody assumes otherwise:

- Audio timing under load. `AudioProcessorUsageMax()` must be read on hardware.
- SGTL5000 register behaviour — no I²C fake.
- BM83 behaviour. The packet codec is tested; the module's responses are not, and it must be
  switched to Host Mode with Microchip's Config Tool before it responds at all
  ([ADR 0003](decisions/0003-bluetooth-bm83.md)).
- The display driver — the panel has not been chosen.
- Real Spotify API responses.

## Local gate

```sh
# firmware
cd Firmware && pio run -e teensy41       # add `&& pio test -e native` once suites exist
# app
cd App && .venv/bin/ruff check .         # add pytest and mypy once modules exist
# cross-project
python3 Tools/check_style.py
python3 Tools/generate_protocol.py --check
```

`.githooks/pre-push` runs the same checks, so local and CI agree. Enable it once:

```sh
git config core.hooksPath .githooks
```
