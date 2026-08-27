# Device wire protocol

The link between the companion app and the firmware, over USB CDC serial.

**`Tools/protocol.toml` is the single source of truth.**

```
Tools/protocol.toml
   ├─► firmware header      (generation parked)
   └─► app Python module    (generation parked)
```

Both generators are written and working, but output is **parked** until each side decides where its
generated file lives. Set `H_OUT` / `PY_OUT` in `Tools/generate_protocol.py` to turn them back on.

With both parked, `--check` still validates the spec itself — duplicate opcodes, malformed entries —
so CI keeps a guard on this file.

```sh
python3 Tools/generate_protocol.py           # regenerate (once outputs are enabled)
python3 Tools/generate_protocol.py --check   # validate spec / check drift (CI runs this)
```

Never hand-edit either generated file.

## Framing

```
┌──────┬────────┬──────────────┬───────────────┬───────────┐
│ sync │ opcode │ length (LE16)│  payload      │ crc (LE16)│
│ 0xA5 │  1 B   │     2 B      │  0..512 B     │    2 B    │
└──────┴────────┴──────────────┴───────────────┴───────────┘
```

- **Sync** `0xA5` marks a frame boundary and carries no information.
- **Length** is little-endian and counts the payload only.
- **CRC** is **CRC-16/CCITT-FALSE** (poly `0x1021`, seed `0xFFFF`) over *opcode + length + payload* —
  everything except the sync byte. Transmitted little-endian.
- Maximum payload is **512 bytes**, matching the USB high-speed CDC packet size. Frame overhead is
  6 bytes.

A CRC rather than a checksum because the link carries bulk audio data, where one flipped bit must
not pass silently.

**Resynchronisation:** the decoder discards anything that is not a sync byte while idle. That is
what lets the link recover on its own after a corrupt frame, rather than one dropped byte killing
a long transfer.

> **Reference vector.** `CRC16("123456789") == 0x29B1`. Both test suites assert this. A frame
> carrying payload `01 02 03 04 05` with opcode `0x21` encodes to
> `a5 21 05 00 01 02 03 04 05 2a f6` on both sides, byte for byte.

## Commands — host to device

| Opcode | Name | Payload |
|---|---|---|
| `0x01` | `PING` | — |
| `0x02` | `GET_INFO` | — |
| `0x03` | `GET_STATUS` | — |
| `0x10` | `LIST_BEGIN` | UTF-8 path prefix |
| `0x11` | `LIST_NEXT` | — |
| `0x20` | `FILE_BEGIN` | `uint32` total size, then UTF-8 path |
| `0x21` | `FILE_CHUNK` | raw bytes |
| `0x22` | `FILE_END` | `uint32` CRC-32 of the whole file |
| `0x23` | `FILE_DELETE` | UTF-8 path |
| `0x30` | `SET_OUTPUT` | one `Output` byte |
| `0x40` | `DECK_LOAD` | `Deck` byte, then UTF-8 path |
| `0x41` | `DECK_TRANSPORT` | `Deck` byte, then `Transport` byte |

## Events — device to host

| Opcode | Name | Payload |
|---|---|---|
| `0x80` | `ACK` | the acknowledged opcode |
| `0x81` | `NACK` | acknowledged opcode, then a `Status` byte |
| `0x82` | `PONG` | — |
| `0x83` | `INFO` | protocol version, SD mounted flag |
| `0x84` | `STATUS` | deck A state, deck B state |
| `0x90` | `LIST_ENTRY` | flags byte, `uint32` size, UTF-8 name |
| `0x91` | `LIST_END` | — |
| `0xF0` | `LOG` | UTF-8 diagnostic text |

## Enumerations

**Status** — `OK 0x00`, `BAD_CRC 0x01`, `BAD_OPCODE 0x02`, `BAD_LENGTH 0x03`, `BAD_STATE 0x04`,
`SD_ERROR 0x05`, `NO_SPACE 0x06`, `NOT_FOUND 0x07`, `UNSUPPORTED 0x08`

**Output** — `ANALOG 0x00`, `BLUETOOTH 0x01`, `USB_HOST 0x02`
*(`USB_HOST` is accepted but always answered `NACK / UNSUPPORTED` — see [ADR 0005](decisions/0005-usb-host-audio.md).)*

**Deck** — `A 0x00`, `B 0x01`  ·  **Transport** — `STOP 0x00`, `PLAY 0x01`, `PAUSE 0x02`, `CUE 0x03`

## File transfer

```
app                                  device
 │── FILE_BEGIN (size, path) ───────►│  opens the file
 │◄────────────────── ACK ───────────│
 │── FILE_CHUNK (≤512 B) ───────────►│  appends, updates running CRC-32
 │◄────────────────── ACK ───────────│
 │        … repeat …                 │
 │── FILE_END (crc32) ──────────────►│  verifies, commits or deletes
 │◄────────────────── ACK ───────────│
```

The device verifies the CRC-32 before committing and **deletes the partial file on mismatch**. A
corrupt track is worse than a missing one: it would fail at play time, far from the transfer that
caused it.

Only one write may be open at a time. The protocol is strictly sequential, so a second
`FILE_BEGIN` is a protocol error rather than something to queue.

## Keeping the two sides honest

Opcodes and constants are generated, so they cannot disagree. The **framing** — the byte layout and
the CRC — has to be implemented once per language, and that is where silent divergence can creep in.

**Neither side is implemented yet.** When each is written, give both the same reference vectors:

```
CRC16("123456789")                  == 0x29B1
encode(FILE_CHUNK, 01 02 03 04 05)  == a5 21 05 00 01 02 03 04 05 2a f6
encode(PING)                        == a5 01 00 00 ac fb
```

Asserting those on both sides turns a divergence into a failing test rather than a link that
mysteriously does not work. Write those tests first — they are the contract between the two
codebases and cost nothing to run.
