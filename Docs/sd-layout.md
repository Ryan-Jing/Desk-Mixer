# SD card layout

## Card

Built-in socket, native **4-bit SDIO** (`BUILTIN_SDCARD`), not SPI. Formatted **FAT32 or exFAT**.

Use a decent card. Sustained read matters: two decks of 16-bit 44.1 kHz stereo is ~352 kB/s
combined, and the audio engine cannot wait.

**Never write to the card while audio is playing.** Card write bursts stall reads, which is the
classic cause of audio dropouts. Transfers happen a few times a year, so this costs nothing in
practice — but it should be a hard interlock in firmware, refusing `FILE_BEGIN` unless both decks
are stopped, rather than a rule the app is trusted to follow.

## Directory structure

Deliberately plain, so the card stays browsable on a computer and needs no index to interpret.

```
/library/
├── Late Night Set/
│   ├── manifest.json
│   ├── New Order - Blue Monday.wav
│   └── Kraftwerk - Numbers.wav
└── Focus/
    ├── manifest.json
    └── ...
```

- **One directory per playlist** directly under `/library`. The directory name *is* the playlist
  name shown on the LCD.
- **Every audio file is 16-bit 44.1 kHz stereo PCM WAV** ([ADR 0002](decisions/0002-wav-not-mp3.md)).
  Files that are not are rejected at load with a specific reason.
- Firmware creates `/library` on first mount if it is absent.

## Names

The companion app sanitises names to **ASCII** before writing: accents transliterate
(`Björk` → `Bjork`), anything else becomes `_`, and an empty result becomes `untitled`.

This is deliberate. The firmware holds names in fixed byte buffers (`LIBRARY_NAME_MAX`, 64 bytes)
and renders them with a simple font, so a multi-byte character risks being truncated mid-sequence
and shown as mojibake.

## Limits

| Limit | Value | Where |
|---|---|---|
| Playlists | 64 | `LIBRARY_MAX_PLAYLISTS` |
| Tracks per playlist | 512 | `LIBRARY_MAX_TRACKS` |
| Name length | 64 bytes | `LIBRARY_NAME_MAX` |
| Path length | 128 bytes | `SD_PATH_MAX` |

Only one playlist's track list is held in RAM at a time — 512 × 64 B is 32 kB, which is
affordable; every playlist's tracks would not be.

## `manifest.json`

Written by the app beside the audio. It records what *should* be present, including tracks that
could not be resolved and why, so a later sync does not have to re-derive intent from filenames.

```json
{
  "name": "Late Night Set",
  "source_id": "spotify:playlist:...",
  "entries": [
    {
      "title": "Blue Monday",
      "artist": "New Order",
      "remote_path": "/library/Late Night Set/New Order - Blue Monday.wav",
      "isrc": "GBAAA8300001",
      "duration_ms": 449000,
      "resolver": "local"
    }
  ],
  "unresolved": ["Some Track — not found in local library"]
}
```

The firmware does not currently read the manifest — it enumerates directories directly, so the
card works even if the manifest is missing or stale. The manifest is for the app and for humans.

## Space

Roughly **10 MB per minute** (176 kB/s). A 32 GB card holds about 50 hours. The app estimates the
transcoded size with `estimate_wav_bytes()` and should check free space before starting, since a
part-written track is worse than one never started.
