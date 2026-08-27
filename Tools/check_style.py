#!/usr/bin/env python3
"""Enforce the Desk-Mixer firmware house style.

The style is mechanical, so it is checked mechanically rather than by review.
Rules enforced (see Firmware/CLAUDE.md for the rationale):

  1. Every file opens with the 100-column Doxygen file-header block.
  2. All banner rules are exactly 100 columns.
  3. Headers carry the four section banners; sources carry the five.
  4. Header guards are #ifndef PATH_FILE_H / #endif // PATH_FILE_H, never #pragma once.
  5. Only the approved Doxygen tags appear.
  6. Doxygen function blocks live in headers, not sources.
  7. No tabs, no trailing whitespace, no line over 100 columns.
  8. No embedded NUL bytes.

Usage:
    python3 Tools/check_style.py                 # check the whole firmware tree
    python3 Tools/check_style.py <paths...>      # check specific files

Requires only the standard library.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIRMWARE = ROOT / "Firmware"

WIDTH = 100
STAR = "/" + "*" * (WIDTH - 2) + "/"
DASH = "/*" + "-" * (WIDTH - 4) + "*/"

HEADER_SECTIONS = ["HEADERS", "GLOBAL VARIABLES", "CLASS DECLARATIONS", "FUNCTION DECLARATIONS"]
SOURCE_SECTIONS = ["HEADERS", "MACROS", "GLOBAL VARIABLES", "FUNCTION PROTOTYPES",
                   "FUNCTION DEFINITIONS"]

# Test suites use their own banner set, matching the house convention for tests:
# HEADERS, HELPERS, one "TESTS: <subject>" band per group, then RUNNER.
TEST_SECTIONS = ["HEADERS", "HELPERS", "RUNNER"]

ALLOWED_TAGS = {"@file", "@author", "@brief", "@version", "@date", "@copyright",
                "@name", "@param", "@return"}
TAG_RE = re.compile(r"@[a-zA-Z_]+")

GENERATED_MARKER = "AUTO-GENERATED"


def band(label: str, source: bool) -> str:
    return (("/* " if source else "// ") + label).ljust(WIDTH - 2) + "*/"


def check(path: Path) -> list[str]:
    """Return a list of style problems found in one file."""
    problems: list[str] = []
    raw = path.read_bytes()
    if b"\x00" in raw:
        problems.append("contains embedded NUL byte(s) — a '\\0' escape was written literally")

    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    is_source = path.suffix == ".cpp"
    # Files outside the repo can be checked too (useful for comparing against a
    # reference project), so fall back to the path as given.
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path

    # 1. file header block
    if not lines or lines[0] != STAR:
        problems.append("line 1 must be the 100-column file-header rule")
    if " * @file " not in text:
        problems.append("missing @file in the header block")

    # 2/7. line-level rules
    for n, line in enumerate(lines, start=1):
        if "\t" in line:
            problems.append(f"line {n}: contains a tab")
        if line != line.rstrip():
            problems.append(f"line {n}: trailing whitespace")
        if len(line) > WIDTH:
            problems.append(f"line {n}: {len(line)} columns, limit is {WIDTH}")
        stripped = line.strip()
        if stripped.startswith("/*-") and len(line) != WIDTH:
            problems.append(f"line {n}: banner rule is {len(line)} columns, must be {WIDTH}")
        # A rule line is all slashes and stars AND long. The 3-character "/**" that
        # opens a Doxygen block is not a rule and must not be measured as one.
        if (len(stripped) > 5 and set(stripped) <= {"/", "*"} and len(line) != WIDTH):
            problems.append(f"line {n}: star rule is {len(line)} columns, must be {WIDTH}")

    # 3. section banners
    is_test = "test" in rel.parts
    if is_test:
        expected = TEST_SECTIONS
        if not any(l.startswith("/* TESTS:") for l in lines):
            problems.append("missing at least one 'TESTS: <subject>' section banner")
    else:
        expected = SOURCE_SECTIONS if is_source else HEADER_SECTIONS
    for label in expected:
        if band(label, is_source) not in lines:
            problems.append(f"missing '{label}' section banner")

    # 4. header guards
    if not is_source and not is_test:
        if "#pragma once" in text:
            problems.append("uses #pragma once; the house style is an #ifndef guard")
        # The guard name is derived from the path below include/, so it can only be
        # checked for files inside this project's include tree.
        try:
            stem = str(rel.relative_to("Firmware/include"))
        except ValueError:
            stem = None
        if stem is not None:
            guard = stem.replace("/", "_").replace(".h", "_H").replace("-", "_").upper()
            if f"#ifndef {guard}" not in text:
                problems.append(f"header guard should be '#ifndef {guard}'")
            if f"#endif // {guard}" not in text:
                problems.append(f"closing guard should be '#endif // {guard}'")

    # 5. approved tags only
    for tag in sorted(set(TAG_RE.findall(text))):
        if tag not in ALLOWED_TAGS:
            problems.append(f"uses disallowed Doxygen tag '{tag}'")

    # 6. Doxygen blocks belong in headers. main.cpp is the documented exception:
    #    it has no header, so its blocks sit on the prototypes.
    if is_source and path.name != "main.cpp" and not is_test and GENERATED_MARKER not in text:
        body = "\n".join(lines[14:])
        if " * @brief" in body:
            problems.append("Doxygen function block in a source file; move it to the header")

    return problems


def main() -> int:
    if len(sys.argv) > 1:
        targets = [Path(a).resolve() for a in sys.argv[1:]]
    else:
        targets = sorted(
            list((FIRMWARE / "include").rglob("*.h"))
            + list((FIRMWARE / "src").rglob("*.cpp"))
            + list((FIRMWARE / "test").rglob("*.cpp"))
        )

    total = 0
    for path in targets:
        if not path.exists() or path.suffix not in {".h", ".cpp"}:
            continue
        problems = check(path)
        if problems:
            try:
                shown = path.relative_to(ROOT)
            except ValueError:
                shown = path
            print(f"\n{shown}")
            for p in problems:
                print(f"  {p}")
            total += len(problems)

    if total:
        print(f"\n{total} style problem(s) found")
        return 1
    print(f"style OK — {len(targets)} file(s) checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
