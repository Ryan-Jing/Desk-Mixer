# Desk-Mixer — Companion App

Reads your Spotify playlists, finds the audio, converts it to the format the device plays, and
transfers it over USB.

**Status: scaffolding only.** `pyproject.toml` and an empty package. Nothing is implemented. This
README is the design and the build order — follow it top to bottom.

---

## What it does

```
Spotify Web API          OAuth 2.0 + PKCE, read-only scopes
      │                  playlists, titles, artists, durations, ISRCs
      ▼
TrackResolver            given metadata, return a local audio file
      │                  the extension point — see below
      ▼
ffmpeg                   → 16-bit 44.1 kHz stereo WAV
      │
      ▼
Serial transfer          FILE_BEGIN → FILE_CHUNK ×N → FILE_END, CRC-32 verified
      │
      ▼
device SD card           /library/<playlist>/<track>.wav
```

Spotify supplies **metadata only**. It is never asked for audio — see
[ADR 0004](../Docs/decisions/0004-track-resolver.md).

---

## Setup

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

`ffmpeg` must be on PATH (`brew install ffmpeg`).

⚠️ **A venv hardcodes absolute paths.** If this directory is ever moved or renamed, delete `.venv`
and recreate it — the console scripts will otherwise point at the old location.

---

## Build order

Each step is independently testable and depends only on the ones above it. Resisting the urge to
start with the UI is the single most useful discipline here — it is the thinnest layer and the most
likely to change.

| # | Build | Why here | Needs |
|---|---|---|---|
| 1 | **Wire protocol** — framing, CRC-16, decoder | Pure byte-in/byte-out. Fully testable with zero dependencies, and the reference vectors already exist | nothing |
| 2 | **Transport** — serial + a loopback fake | The fake is what lets steps 7–8 be built and tested without hardware | pyserial |
| 3 | **Transcode** — ffmpeg wrapper | Small, self-contained, and the output format is already fixed | ffmpeg |
| 4 | **Resolver interface** + local-library resolver | Defines the contract before anything depends on it. No network | mutagen |
| 5 | **Spotify auth + client** | First step needing credentials and network | requests, a client ID |
| 6 | **YouTube resolver** | Slots into the step-4 contract | yt-dlp |
| 7 | **Manifest + library index** | Needs the resolver to have something to record | — |
| 8 | **Transfer orchestration** | Ties 1–7 together | — |
| 9 | **UI** | Last. Thin by design | PySide6 |

A useful checkpoint: after step 3 you can transcode a file by hand; after step 8 you have a working
CLI and the device can be loaded. The UI is genuinely optional until then.

---

## Layering

```
spotify/     OAuth PKCE + Web API client   — metadata only, never audio
resolve/     TrackResolver contract + implementations
transcode/   ffmpeg wrapper
device/      protocol, transport, transfer
library/     playlist manifests, SD index
ui/          PySide6 views
```

**`ui/` may call anything; nothing may call `ui/`.** Everything else must be usable headless —
that is what makes it testable and what keeps a CLI possible. If logic is hard to test, it is
almost always in the wrong layer.

---

## Implementation notes

### 1. Wire protocol

Full spec in [`Docs/protocol.md`](../Docs/protocol.md). Opcodes and constants come from
`Tools/protocol.toml` — generation is currently parked, so either hand-write them and keep them in
step, or point `PY_OUT` in `Tools/generate_protocol.py` at wherever the module should live and let
it emit them.

```
┌──────┬────────┬──────────────┬───────────────┬───────────┐
│ sync │ opcode │ length (LE16)│  payload      │ crc (LE16)│
│ 0xA5 │  1 B   │     2 B      │  0..512 B     │    2 B    │
└──────┴────────┴──────────────┴───────────────┴───────────┘
```

CRC is **CRC-16/CCITT-FALSE** (poly `0x1021`, seed `0xFFFF`) over *opcode + length + payload* —
everything except the sync byte. Max payload 512 bytes, matching the USB high-speed CDC packet.

The decoder must **discard anything that is not a sync byte while idle**. That is what lets the link
recover after a corrupt frame instead of one dropped byte killing a long transfer.

> **Pin these with tests from the start.** The firmware implements the same framing independently,
> so these vectors are what turn a silent divergence into a failing test:
> ```
> crc16(b"123456789")                     == 0x29B1
> encode(FILE_CHUNK, 01 02 03 04 05).hex() == "a52105000102030405" "2af6"
> encode(PING).hex()                       == "a5010000acfb"
> ```

### 2. Transport

Wrap pyserial behind a small `Protocol` interface with `write` / `read` / `close`, then write a
`LoopbackTransport` that records what was written and can hand back scripted replies.

That fake is worth building *before* anything uses it: it lets the whole transfer flow — including
the device rejecting a command — be exercised with no hardware attached. Teensy USB VID is `0x16C0`
for port auto-detection.

### 3. Transcode

The device plays one format only, so every source funnels through this:

```
ffmpeg -hide_banner -loglevel error -nostdin -y -i <src>
       -map a:0 -vn -ar 44100 -ac 2 -acodec pcm_s16le -f wav <dst>
```

**Build the argument vector separately from running it.** Then the command can be asserted in tests
without invoking ffmpeg, which keeps the test suite fast and hermetic.

Size estimate for space checks before a transfer: `44 + (duration_ms × 44100 / 1000) × 2 × 2` bytes,
about **10 MB per minute**. Check free space before starting — a part-written track is worse than
one never started.

On failure, delete the partial output. A truncated WAV fails at play time, far from the transfer
that caused it.

### 4. Resolver

The extension point that keeps the core neutral about where audio comes from:

```python
class TrackResolver(Protocol):
    name: str
    def resolve(self, track: TrackMeta) -> ResolveResult: ...
```

Two rules that matter:

- **Never raise for an unresolvable track.** Return a failed result carrying a *reason*. One bad
  track must not abort a playlist of sixty.
- **Report the best failure**, not the last one, when everything misses — the user needs to know
  *why* nothing matched.

`LocalLibraryResolver` matches **ISRC first** (exact, confidence 1.0), then normalised
artist/title. Normalisation should strip accents, punctuation, and **bracketed qualifiers** —
"Song (Remastered 2011)" and "Song [Live]" are the single largest cause of false negatives across
catalogues. Fall back to filename parsing (`Artist - Title.ext`) when tags are missing; a file
without tags is not an error.

### 5. Spotify

OAuth 2.0 with **PKCE** — this is a desktop app and therefore a public client, so there is no
secret to protect. Scopes are read-only: `playlist-read-private`, `playlist-read-collaborative`.
The app must never request write access.

- Verifier: 64 random bytes, base64url, unpadded. Challenge: S256 of the verifier, base64url,
  unpadded.
- Redirect to a **loopback** URI (`http://127.0.0.1:<port>/callback`); carry an opaque `state` and
  check it on return.
- Endpoints: `GET /v1/me/playlists`, `GET /v1/playlists/{id}/tracks`. Both paginate — follow `next`.
- Skip `is_local` tracks and null entries; playlist payloads routinely contain both.
- Pull **ISRC** from `external_ids` — it is by far the most reliable match key.

⚠️ **Access is single-user.** Spotify apps stay in development mode (~25 manually-added users)
unless they grant a quota extension, which they rarely do for non-commercial projects. Accepted:
this is Ryan's own device.

Map the API payload to `TrackMeta` in a **free function**, so it can be tested against captured JSON
with no network.

### 6. YouTube resolver

Slots into the step-4 contract. Two things to plan for:

- **`yt-dlp` breaks whenever the site changes.** Treat it as a dependency needing maintenance, and
  fail with a clear message rather than a stack trace.
- **Matching is the real problem, not downloading.** Covers, live takes and sped-up edits all
  resolve to plausible-looking videos. **Duration is the cheapest sanity check** — reject anything
  more than a few seconds from the Spotify metadata, and prefer results whose title contains the
  artist.

Quality context: lossy → WAV **preserves** the source, it does not improve it. Given the device ends
in SBC Bluetooth or a modest headphone amp, that is a fine trade — see
[ADR 0004](../Docs/decisions/0004-track-resolver.md).

### 7. Manifest

Written beside the audio on the card. Records what *should* be present, **including what could not
be resolved and why**, so a later sync does not have to re-derive intent from filenames.

```json
{
  "name": "Late Night Set",
  "source_id": "spotify:playlist:...",
  "entries": [
    { "title": "...", "artist": "...", "remote_path": "/library/Late Night Set/....wav",
      "isrc": "...", "duration_ms": 449000, "resolver": "local" }
  ],
  "unresolved": ["Some Track — not found in local library"]
}
```

The firmware does not read it — it enumerates directories directly, so the card works even if the
manifest is stale or missing. This is for the app and for humans.

### 8. Transfer

```
FILE_BEGIN (uint32 size, utf-8 path) ──► ACK
FILE_CHUNK (≤512 B)                  ──► ACK    … repeated
FILE_END   (uint32 crc32)            ──► ACK
```

CRC-32 is IEEE 802.3 (`zlib.crc32`), computed over the whole file. The device verifies before
committing and deletes the partial file on mismatch.

⚠️ **Never transfer while the device is playing.** SD write bursts stall the reads feeding the audio
engine, which is the classic dropout cause. The firmware should enforce this as a hard interlock,
but the app should not attempt it either.

Names are sanitised to **ASCII** before writing: transliterate accents (`Björk` → `Bjork`), replace
anything else with `_`, and never produce an empty name. The firmware holds names in fixed byte
buffers and renders them with a simple font, so a multi-byte character risks being truncated
mid-sequence.

### 9. UI

Thin. It owns no business logic — everything it shows comes from the headless layers. A playlist
list, a transfer button, a progress bar and a status line covering device presence and ffmpeg
availability is enough for v1.

---

## Testing

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/mypy
```

**No test may touch the network, a real serial port, or a real ffmpeg binary.** That is achievable
throughout if the layering above holds:

| Area | How to test it hermetically |
|---|---|
| protocol | reference vectors, round trips, corruption, resynchronisation |
| transport | `LoopbackTransport` playing a fake device that ACKs or NACKs |
| transcode | assert the argument vector; never invoke ffmpeg |
| resolver | a `tmp_path` folder of dummy audio files |
| spotify | captured JSON payloads through the mapping function |
| transfer | loopback fake, including the rejection paths |

Write the protocol tests **first** — they are the contract with the firmware, and they cost nothing
to run.

---

## Configuration and secrets

Nothing secret belongs in the repository. PKCE needs no client secret, but a **client ID** from the
Spotify developer dashboard is required.

```
~/.config/desk-mixer/settings.json        client ID, music folders, serial port, ffmpeg path
~/.config/desk-mixer/spotify-token.json   cached token — chmod 0600
```

Use `platformdirs` rather than hardcoding, and make loading tolerant of a missing or corrupt file by
falling back to defaults.

A `--doctor` command that reports ffmpeg availability, visible serial ports, configured music
folders and whether a client ID is set is worth building early — it must work **without PySide6**,
so import the UI lazily.
