# Audio architecture

## The deadline

The Teensy Audio Library processes **128 samples at 44.1 kHz** — one block every **2.9 ms**,
344 times a second. Every audio object's `update()` runs inside that window at interrupt priority.

This single number governs the design. Overrunning it does not slow the device down; it drops
audio.

**Inside any `update()` or audio callback: no heap, no blocking, no `Serial`, no unbounded loops.**

## Graph

```
                     ┌────────────────────┐
AudioPlaySdResmp A ─►│ FilterStateVariable │─┐
   (SD, varispeed)   └────────────────────┘ │   ┌───────────┐
                                            ├──►│ Mixer L/R │──┬──► AudioOutputI2S   ──► SGTL5000 ──► 3.5 mm jack
                     ┌────────────────────┐ │   └───────────┘  │
AudioPlaySdResmp B ─►│ FilterStateVariable │─┘                 ├──► AudioOutputI2S2  ──► BM83 ──► Bluetooth
   (SD, varispeed)   └────────────────────┘                    │
                                                               └──► [USB host — no driver]
        │                                                                 (ADR 0005)
        └──► AudioAnalyzePeak ×2 ──► LCD level meters
```

Worth building in one place that owns **every** `AudioStream` object, so the graph can be read as a
whole and the block budget has a single home.

## Why both outputs are always fed

`AudioOutputI2S` and `AudioOutputI2S2` are separate peripherals (SAI1 and SAI2) and run
concurrently. Both mixer outputs are connected permanently; selecting an output changes what the
UI presents as active rather than muting a sink. Muting on switch would add a click every time,
for no benefit.

Feeding the BM83 over I2S2 means Bluetooth is fed **digitally** — no DAC→wire→ADC round trip.

## Playback and tempo

`AudioPlaySdResmp` from [`teensy-variable-playback`](https://github.com/newdigate/teensy-variable-playback)
resamples on the fly, so tempo and pitch move together — varispeed, like a turntable, not
time-stretch. Key-lock (WSOLA) would cost roughly half a core when active and is out of scope for v1.

Tempo range is ±8 % (`DSP_TEMPO_RANGE_PERCENT`), with a centre detent that yields **exactly 1.0**
so a centred fader is bit-accurate playback.

### Transport semantics — read this before designing the deck API

The library's API is narrower than it looks:

- `playWav(path)` is the **only** way to start. It opens the file and begins at the configured
  play-start point.
- `stop()` clears the playing flag but **does not rewind**.
- There is **no `play()`** on `AudioPlaySdResmp` and no seek.

So pause/resume is expressed as *set the play-start point, then re-open*:

| Action | Implementation |
|---|---|
| play from top | `setPlayStart(play_start_sample, 0)` → `playWav(path)` |
| pause | record `positionMillis()`, then `stop()` |
| resume | `setPlayStart(play_start_arbitrary, frames)` → `playWav(path)` |
| cue | `stop()`, clear the stored resume position |

`_playback_start` is in **frames** (per-channel samples), not bytes or milliseconds:
`frames = ms × 44100 / 1000`.

## Mixing law

`dsp_crossfade_gains()` uses a **constant-power** sin/cos law, so `gain_a² + gain_b² == 1` across
the whole sweep and a centred crossfader is not quieter than either extreme. Channel faders use a
squared taper (`dsp_fader_to_gain`), because a linear fader feels top-heavy — loudness perception
is logarithmic, so the bottom half of a linear fader is nearly unusable.

Both laws are pure arithmetic with no hardware dependency, so they are natural candidates for host
unit tests — the constant-power invariant in particular is easy to assert across the full sweep.

## Budget

The Teensy 4.1 has 7.75 MB flash and 512 kB RAM. The current scaffold uses ~9.5 kB, so essentially
all of it is available.

`AudioMemory(n)` allocates the audio block pool — around 60 is a reasonable starting point. Tune it
against `AudioMemoryUsageMax()` and `AudioProcessorUsageMax()` on hardware; if memory usage reaches
the allocation, blocks are being starved and it will be audible. Keep peak CPU well under ~70 % so
transients have headroom.

Teensy 4.1 has pads for **8 MB PSRAM**, and `AudioPlaySdResmp` can buffer there
(`setBufferInPSRAM`). Worth fitting at assembly: it is painful to add later.

## Bluetooth latency

SBC adds roughly 150–300 ms. The analog jack is the monitoring output used for beat-matching;
Bluetooth is an audience output. The UI must not present Bluetooth-derived metering as real-time.
