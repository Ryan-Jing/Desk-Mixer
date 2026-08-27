# Desk-Mixer — Teensy 4.1 Firmware

PlatformIO / Arduino framework. Read the root `CLAUDE.md` first for project-wide facts.

**This firmware is written by Ryan.** The architecture is worked out together, but the module
breakdown, folder names and implementation are his. Do not scaffold subsystems, invent a folder
layout, or write implementation code unless asked — offer design options and let him choose.

## Style is not negotiable

Every file matches the house style exactly. It is mechanical — copy the templates below rather than
approximating them. `python3 ../Tools/check_style.py` enforces it and runs in CI.

- **All banner rules are exactly 100 characters.** Not 98, not 102.
- **4-space indent, no tabs, no trailing whitespace.**
- Doxygen blocks go **in headers only**. Source files carry the file header and section banners and
  nothing else — no per-function blocks in `.cpp`. (`main.cpp` is the exception: it has no header,
  so its blocks sit on the prototypes.)
- Allowed Doxygen tags: `@file @author @brief @version @date @copyright @name @param @return`.
  **Do not use** `@note @warning @retval @details @param[in]`.
- Header guards are `#ifndef PATH_FILE_H` / `#endif // PATH_FILE_H` derived from the include path.
  **Never `#pragma once`.**
- Section banners appear **even when the section is empty**, in a fixed order.

### File header — every file, including tests

```c
/**************************************************************************************************/
/**
 * @file example.cpp
 * @author  Ryan Jing
 * @brief One-line statement of what this file is for.
 *
 * @version 0.1
 * @date 2026-08-26
 *
 * @copyright Copyright (c) 2026
 *
 */
/**************************************************************************************************/
```

### Section banners — headers use // , sources use /*

`.h` — four sections, in this order:

```c
/*------------------------------------------------------------------------------------------------*/
// HEADERS                                                                                        */
/*------------------------------------------------------------------------------------------------*/
```
then `GLOBAL VARIABLES`, `CLASS DECLARATIONS`, `FUNCTION DECLARATIONS`.

`.cpp` — five sections, in this order:

```c
/*------------------------------------------------------------------------------------------------*/
/* HEADERS                                                                                        */
/*------------------------------------------------------------------------------------------------*/
```
then `MACROS`, `GLOBAL VARIABLES`, `FUNCTION PROTOTYPES`, `FUNCTION DEFINITIONS`.

Test suites use their own set: `HEADERS`, `HELPERS`, one `TESTS: <subject>` band per group, then
`RUNNER`.

### Function documentation — headers only

```c
/**************************************************************************************************/
/**
 * @name
 * @brief What it does, in one sentence.
 *
 *
 * @param deck
 * @param ratio
 *
 * @return true
 * @return false
 */
/**************************************************************************************************/
bool deck_set_speed(DeckId deck, float ratio);
```

## Naming

| Element | Convention |
|---|---|
| Files | `snake_case.cpp` / `.h` |
| Functions | `snake_case`, **prefixed with their module** — `led_init`, `bm83_send` |
| Types | `PascalCase` — `DeckState`, `WavInfo` |
| Enums | unscoped `enum`, `SCREAMING_SNAKE` members, domain-prefixed — `DECK_STOPPED` |
| Structs | `typedef struct Name { ... } Name;`, `snake_case` fields |
| Constants | `#define` in `SCREAMING_SNAKE`. **`constexpr` is not used in this codebase** |
| File-static | `s_` prefix; cross-task globals `g_` |

No namespaces. No `enum class`. `nullptr`, not `NULL`. `}` on its own line before `else {`.

## Layout

`include/` mirrors `src/`, and there is **no `lib/` folder** — that much follows Ryan's existing
projects. **The subsystem breakdown and folder names are his to decide**, and are not settled yet.
Do not assume a structure or create folders speculatively.

## Real-time rules — the audio path

The audio engine runs at interrupt priority with a **2.9 ms budget per 128-sample block**. Inside
any `update()` or audio-callback path:

- **No heap.** No `malloc`, `new`, `String`, `std::vector`, or anything that allocates.
- **No blocking.** No `delay()`, no busy-wait, no SD access outside the player objects.
- **No `Serial`.** Logging from the audio path will cause dropouts.
- No unbounded loops. Everything is O(block size).

`main.cpp` runs a cooperative superloop at fixed cadences. Nothing in it may busy-wait or `delay()`.

## Testing

```sh
pio run -e teensy41          # build
pio test -e native           # host unit tests
pio test -e teensy41_test    # on-target tests — needs hardware attached
```

- **There is no Teensy 4.1 emulator.** No Renode or QEMU machine model exists for the i.MX RT1062,
  and the peripherals that matter (SAI/I2S, SDIO) are not modelled anywhere. Do not propose
  emulation-based testing. Host tests plus hardware fakes are the substitute.
- Code that includes no Arduino or Teensy headers can be compiled and tested on the host. Listing
  such a file in `[pure] sources` in `platformio.ini` is what makes `pio test -e native` pick it
  up. Suggest this split where it fits, but the decision is Ryan's.
- PlatformIO takes over the first `Serial` as its on-target test transport, so **all `Serial` use
  must sit inside `#ifndef UNIT_TEST`**.

## Debug output

Guarded by `PRINT_DEBUG`, with the body indented inside the directives:

```c
    #ifdef PRINT_DEBUG
        Serial.println("Deck A loaded");
    #endif
```
