# Desk-Mixer — Laptop Companion App

Python 3.11+ / PySide6. Read the root `CLAUDE.md` first for project-wide facts.

**Nothing is implemented yet.** The package is empty scaffolding. `README.md` holds the design, the
layering, and a **build order** — follow that order rather than jumping ahead, and do not scaffold
modules speculatively. Each step there is chosen so it can be built and tested before the next one
depends on it.

## Layering

```
spotify/     OAuth PKCE + Web API client   — metadata only, never audio
resolve/     TrackResolver contract + implementations
transcode/   ffmpeg wrapper
device/      protocol, transport, transfer
library/     playlist manifests, SD index
ui/          PySide6 views
```

**`ui/` may call anything; nothing may call `ui/`.** Everything else must be usable headless — that
is what makes it testable and keeps a CLI possible. If logic is hard to test, it is in the wrong
layer.

## Rules

- **Spotify is metadata only.** Playlists, titles, artists, ISRCs. Never add code that downloads or
  extracts audio from Spotify — it breaches their Terms and the Developer Terms, and risks the
  user's API client. Audio comes from a resolver. See ADR 0004.
- **A resolver never raises for an unresolvable track.** It returns a failed result carrying a
  reason. One bad track must not abort a playlist.
- **Never transfer while the device is playing.** SD write bursts stall the reads feeding the audio
  engine. The firmware enforces this; the app should not attempt it either.
- **Secrets never enter the repo.** Client ID and cached tokens live in the OS config directory via
  `platformdirs`, not in source and not in a committed `.env`. The token file is `0600`.
- Every public function gets a type hint; `mypy` runs in CI. Docstrings on every public module,
  class and function, Google style — the firmware's Doxygen convention does not apply here.

## Wire protocol

The spec is `Tools/protocol.toml` and `Docs/protocol.md`. Generation into both sides is currently
**parked** — set `H_OUT` / `PY_OUT` in `Tools/generate_protocol.py` to turn it back on once each
side has decided where its generated file lives.

The framing is implemented once per language, so the two implementations are pinned together by
shared reference vectors. Keep them:

```
crc16(b"123456789")                      == 0x29B1
encode(FILE_CHUNK, 01 02 03 04 05).hex()  == "a52105000102030405" "2af6"
encode(PING).hex()                        == "a5010000acfb"
```

## Testing

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/mypy
```

**No test may touch the network, a real serial port, or a real ffmpeg binary.** Build the
`LoopbackTransport` fake early — it is what lets the whole transfer flow, including rejection paths,
run with no hardware. Assert the ffmpeg argument vector rather than invoking ffmpeg.

⚠️ A venv hardcodes absolute paths. If this directory is moved or renamed, delete `.venv` and
recreate it.
