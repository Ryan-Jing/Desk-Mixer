# Configuring Claude Code for this project

Written for someone setting up a project's AI configuration for the first time. It explains the
four mechanisms, when each is the right tool, and how this repository uses them.

The short version: **`CLAUDE.md` holds facts that are always true. Skills hold procedures you
invoke. Settings hold permissions. Hooks hold automation.** Most confusion comes from putting a
thing in the wrong one of those four.

---

## 1. The four mechanisms

| Mechanism | Lives in | Loaded | Good for |
|---|---|---|---|
| **`CLAUDE.md`** | repo root and subdirectories | automatically, every session | facts, constraints, conventions |
| **Skills** | `.claude/skills/<name>/SKILL.md` | when the model judges it relevant, or you type `/name` | multi-step procedures, checklists |
| **Settings** | `.claude/settings.json` | automatically | permissions, environment |
| **Hooks** | inside `settings.json` | on tool events | enforcement that must not be skipped |

### The distinction that matters most

**`CLAUDE.md` is always in context, so every line costs you.** A 500-line `CLAUDE.md` crowds out
the actual code. Put only what must be true in *every* conversation there.

**A skill costs nothing until it is used.** Long procedures, rarely-needed checklists and anything
conditional belong in a skill.

A useful test: *"Would I want this read before every single message?"* If no, it is a skill.

---

## 2. `CLAUDE.md` — one file or several?

You asked this directly. The answer for a monorepo like this one is **several**, arranged
hierarchically.

Claude Code reads the **root `CLAUDE.md` every session**, and picks up a **subdirectory's
`CLAUDE.md` when it works on files in that subdirectory**. So a nested file costs nothing while
you are working elsewhere.

This repository uses that shape:

```
Desk-Mixer/
├── CLAUDE.md             ← always loaded: repo map, hard facts, routing
├── Firmware/CLAUDE.md    ← only when touching firmware
├── App/CLAUDE.md         ← only when touching the app
└── Electrical/CLAUDE.md    ← only when touching the PCB
```

**What goes in the root file**

- A repository map, so the first question is never "where does this live?"
- **Hard facts that must not be silently re-derived.** This is the highest-value content in the
  whole setup. Our root file records that the SD card holds WAV not MP3, that USB host audio has
  no driver, and that Spotify is metadata-only. Without those, every new session risks
  cheerfully rebuilding something that was already decided and rejected — expensively.
- Pointers to the sub-project files.

**What goes in a sub-project file**

Anything only true inside it. The firmware file carries the byte-exact banner templates, the
real-time rules, and the pure/impure split. None of that is relevant while editing Python, so
none of it should be loaded then.

**What does *not* belong in any `CLAUDE.md`**

- Anything the code already says. It will drift, and the code wins.
- Long tutorials. Those are skills or `Docs/`.
- Aspirations. Write what is true now.

### Other placements

- `~/.claude/CLAUDE.md` — applies to *every* project you open. Good for personal style ("prefer
  British spelling"), bad for anything project-specific.
- `@path/to/file.md` inside a `CLAUDE.md` imports another file, which keeps the top-level file
  short.
- Typing `#` at the start of a message asks Claude to save a note to memory — the quickest way to
  capture a rule the moment you find yourself repeating it.

---

## 3. Skills

A skill is a folder containing `SKILL.md` with YAML frontmatter:

```markdown
---
name: firmware-module
description: Scaffold a new firmware subsystem module in the house style. Use when adding a
  new subsystem to the Teensy firmware, or when asked to create a new .h/.cpp pair.
---

# Steps

1. ...
```

The **`description` is the trigger.** The model reads descriptions to decide whether to load a
skill, so write it as *when to use this*, not *what this is*. "Scaffold a firmware module" is a
poor description; "Use when adding a new subsystem to the Teensy firmware" is a good one.

You can also invoke a skill explicitly by typing `/firmware-module`.

A skill folder can bundle scripts and reference files next to `SKILL.md`. That is often better
than describing a procedure in prose — our `doxygen-style` skill ships an actual checker rather
than explaining the rules again.

### The five skills in this repo

| Skill | Use when |
|---|---|
| `firmware-module` | adding a subsystem — generates the mirrored `.h`/`.cpp` with exact banners |
| `doxygen-style` | checking or fixing house style; runs `Tools/check_style.py` |
| `audio-graph` | touching the audio graph — CPU/memory budgeting and the 2.9 ms rules |
| `protocol-sync` | changing the wire protocol — regenerates both sides from the TOML |
| `preflight` | before committing — runs the whole local gate and reports a table |

Each earns its place by being repetitive and rule-heavy. **A skill that just restates `CLAUDE.md`
is worse than no skill**: it is another thing to keep in sync.

---

## 4. Settings and permissions

`.claude/settings.json` is committed and shared. `.claude/settings.local.json` is personal and
git-ignored.

The most immediately useful thing here is an allow-list, so routine read-only commands stop
prompting:

```json
{
  "permissions": {
    "allow": [
      "Bash(pio run:*)",
      "Bash(pio test:*)",
      "Bash(python3 Tools/check_style.py:*)"
    ]
  }
}
```

Two cautions worth internalising:

- Allow-list **read-only and idempotent** commands freely. Be deliberate about anything that
  writes, uploads, or pushes.
- Never allow-list `git push` or `git commit`. This repo's `CLAUDE.md` also says not to commit
  unless asked — belt and braces.

---

## 5. Hooks

Hooks run **your own shell commands** on tool events — `PreToolUse`, `PostToolUse`,
`UserPromptSubmit`, `Stop` and others. A `PreToolUse` hook can block a tool call.

The distinction from `CLAUDE.md`: a rule in `CLAUDE.md` is an instruction the model should follow;
a hook is machinery that runs whether or not the model cooperates. **If a rule genuinely must not
be violated, it wants a hook, not a sentence.**

For example, to run the style checker after every firmware edit:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 Tools/check_style.py 2>&1 | tail -5"
          }
        ]
      }
    ]
  }
}
```

This repo does **not** ship that hook, deliberately — it would run on every edit including the
Python app, where it is meaningless. The `.githooks/pre-push` gate covers the same ground at a
more sensible moment. Add the hook if you find style drift is actually happening.

---

## 6. Subagents

`.claude/agents/*.md` defines a subagent with its own context window and tool set. It is the right
tool when a task would otherwise flood your main conversation with output — a wide codebase search,
say — and you only need the conclusion.

Subagents cost a fresh context each time and cannot see your conversation, so they are not free.
This repo does not define any yet; the built-in general-purpose ones are enough at its current
size.

---

## 7. Deciding where something goes

```
Is it a fact that is always true?
   └─ yes ─► CLAUDE.md   (root if global, sub-project if scoped)
   └─ no
      │
      Is it a procedure with steps?
         └─ yes ─► skill
         └─ no
            │
            Must it be enforced mechanically?
               └─ yes ─► hook (or a git hook / CI job)
               └─ no ─► Docs/, and link it from CLAUDE.md
```

---

## 8. Keeping it honest over time

The failure mode for this kind of setup is not writing too little; it is letting it drift until it
is confidently wrong. Practical habits:

- **When a decision is made, write the ADR then**, not later. `Docs/decisions/` exists for this.
  Three of ours record decisions that had already silently changed in the schematic and were never
  written down — that is the state to avoid.
- **When you correct Claude twice on the same thing, that is a `CLAUDE.md` line.** Once is a
  mistake; twice is a missing rule.
- **Prefer generated over documented.** `Tools/protocol.toml` generates both protocol
  implementations, so they cannot disagree. A generator beats a paragraph asking two files to be
  kept in sync.
- **Prefer checked over asked.** `Tools/check_style.py` enforces the house style mechanically, so
  `CLAUDE.md` can state the rule once and point at the checker.
- **Reread the root `CLAUDE.md` every few months** and delete what is no longer true.

## 9. Where to start if you are extending this

1. Work normally, and notice when you repeat yourself.
2. Repeating a *fact* → add a line to the nearest `CLAUDE.md`.
3. Repeating a *procedure* → write a skill.
4. Repeating a *correction* → consider a hook or a checker.
5. Making an architectural *decision* → write an ADR.

Nothing here needs to be got right up front. The configuration is meant to grow out of friction
you actually hit.
