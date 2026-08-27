# Teensy 4.1 pin map

**Source of truth for firmware.** Derived from `Electrical/Desk-DJ.kicad_pcb`. Where this
disagrees with the schematic, **the schematic wins** — flag it rather than editing either side
silently. This document is the reference the firmware should be written against.

## Fixed-function pins

These are fixed by the i.MX RT1062 silicon and are **not reassignable**.

| Pin | Signal | Peripheral | Goes to |
|---|---|---|---|
| 7 | `I2S1_TX` / **TX_DATA0** | SAI1 | SGTL5000 `I2S_DIN` (pin 17) |
| 8 | `I2S1_RX` / **RX_DATA0** | SAI1 | SGTL5000 `I2S_DOUT` (pin 16) |
| 20 | `I2S1_LRCLK` | SAI1 | SGTL5000 |
| 21 | `I2S1_BCLK` | SAI1 | SGTL5000 |
| 23 | `I2S1_MCLK` | SAI1 | SGTL5000 |
| 2 | `I2S2_TX` / TX_DATA | SAI2 | BM83 `DT1` (pin 4) |
| 3 | `I2S2_LRCLK` | SAI2 | BM83 `RFS1` (pin 2) |
| 4 | `I2S2_BCLK` | SAI2 | BM83 `SCLK1` (pin 3) |
| 5 | `I2S2_RX` / RX_DATA | SAI2 | BM83 (unused — TX only) |
| 33 | `I2S2_MCLK` | SAI2 | BM83 `MCLK1` (pin 5) — **required** in slave mode |
| 14 | `SPDIF_OUT` | SPDIF3 | **spare** — a possible feed for a UAC bridge (ADR 0005) |
| 18 | `I2C_SDA` | LPI2C | SGTL5000 (`0x0A`), TUSB320 |
| 19 | `I2C_SCL` | LPI2C | SGTL5000, TUSB320 — ⚠️ see note |
| — | SDIO ×6 | USDHC1 | built-in microSD (`BUILTIN_SDCARD`) |

> ⚠️ Two schematic issues affect this table, both recorded in
> [ADR 0006](decisions/0006-electrical-review.md):
>
> 1. Teensy pin 19 sits on a net named `I2C_SDL` while the codec is on `I2C_SCL`.
> 2. **The I2S1 data lines are swapped at the Teensy.** Pad 7 carries `I2S1_TEENSY_IN` but is the
>    silicon's `TX_DATA0`; pad 8 carries `I2S1_TEENSY_OUT` but is `RX_DATA0`. As drawn, the codec's
>    `I2S_DOUT` and the Teensy's transmitter drive the same net. I2S2 is wired correctly.

## Display — SPI

Panel not yet selected. These follow the `DISP_*` nets already assigned.

| Pin | Net | Function |
|---|---|---|
| 6 | `DISP_BCKLT` | backlight enable |
| 9 | `DISP_DC` | data/command |
| 10 | `DISP_CS` | chip select |
| 11 | `DISP_MOSI` | SPI MOSI |
| 12 | `DISP_MISO` | SPI MISO |
| 13 | `DISP_SCK` | SPI clock |
| 32 | `DISP_RST` | reset |

## Bluetooth and power sequencing

| Pin | Net | Function |
|---|---|---|
| 0 / 1 | `RX1` / `TX1` | `Serial1` → BM83 `HCI_RXD` (13) / ← `HCI_TXD` (12) |
| 28 | `BM83_EN` | BM83 supply enable |
| *TBD* | `BM83_MFB` | BM83 `MFB` (pin 26) — ⚠️ **unassigned**. High 2–3 ms before every UART command |
| *TBD* | `BM83_RST_N` | BM83 `RST_N` (pin 43) — ⚠️ **unassigned**. Active low; also wanted on a button |
| *TBD* | `BM83_P3_4` | BM83 `P3_4` (pin 31) — ⚠️ **unassigned**. High = app mode, low = test/flash mode |
| 29 | `3V3_EN` | 3.3 V rail enable |
| 34 | `3V3_PG` | 3.3 V power-good |
| 30 | `USBC_AUDIO_DET` | USB-C audio port detect |
| 35 | `USBC_AUDIO_EN` | USB-C audio port switch enable |
| 31 | `USBC_5V_FLT` | 5 V current-limit fault |

## Control surface

`USR_CTRL_0..9` are netlisted on the Teensy but `Interface.kicad_sch` is empty, so the
allocation below is **provisional**.

| Pin | Net | Provisional use |
|---|---|---|
| 14 | `USR_CTRL_0` | crossfader |
| 15 | `USR_CTRL_1` | deck A gain |
| 16 | `USR_CTRL_2` | deck B gain |
| 17 | `USR_CTRL_3` | deck A tempo |
| 24 | `USR_CTRL_4` | deck B tempo |
| 25 | `USR_CTRL_5` | deck A filter |
| 26 | `USR_CTRL_6` | deck B filter |
| 27 | `USR_CTRL_7` | *unassigned* |
| 38 | `USR_CTRL_8` | select button |
| 39 | `USR_CTRL_9` | back button |

Pins 14–17 and 24–27 are ADC-capable, which is why the pots sit there. Encoders, when added,
should go on the hardware quadrature timer pins so decoding costs no CPU.

## USB

| Bus | Where | Carries |
|---|---|---|
| Device | micro-USB, reached by **pogo pins to the bottom-side D+/D− test pads** | 5 V power, flashing, companion-app link |
| Host | 5-pin header | intended USB-C audio out — **no driver**, see [ADR 0005](decisions/0005-usb-host-audio.md) |

⚠️ The micro-B receptacle and the bottom D+/D− pads are the **same electrical node**. Only one may
be connected at a time; back-powering a host port can damage the host controller.

## Jack insertion detect

`J3` is an **SJ1-3525N**, the tip-and-ring switch variant: pin 1 sleeve, 2 tip, 3 ring,
**10 tip switch**, **11 ring switch**. The switches are normally closed to their contacts and open
when a plug is inserted, so insertion detection is possible.

The nets `TIP_SW_DET` and `RING_SW_DET` exist on `J3` but are **one-ended** — they do not reach a
GPIO yet, and no Teensy pin is allocated.

Because the switch shorts to the *tip*, which is an audio node, a plain pull-up will not work —
both states read high. A network that does work:

- **1 MΩ pull-up** from pin 10 to +3V3
- **100 kΩ** from the jack-side tip to GND
- series resistor plus a small cap at the GPIO, for ESD and debounce

No plug: the divider reads roughly 0.3 V (low). Plug inserted: pin 10 floats to 3.3 V (high). The
100 kΩ is negligible against a 32 Ω headphone load.

## Unassigned

Pins **22, 36, 37, 40, 41** are free — five pins against four known claimants:

| Wanted for | Why |
|---|---|
| `BM83_MFB` | wake the module before every UART command |
| `BM83_RST_N` | reset, and part of the flash-mode entry sequence |
| `BM83_P3_4` | boot mode select — this is what makes in-system flashing possible |
| jack detect | headphone insertion |

That leaves one spare. Pins 24–27 are partly spoken for by the control surface above.
