#!/usr/bin/env python3
"""Build the Word manual from the Markdown sources.

    python3 docs/build-docx.py

Concatenates the chapters in reading order, rewrites the cross-file links that
mean nothing in Word, and hands the result to pandoc.  Regenerate after editing
any chapter - the Markdown files are the source, the .docx is the artefact.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

DOCS = Path(__file__).resolve().parent
OUTPUT = DOCS / "AcademiSync-Documentation.docx"

CHAPTERS = [
    "README.md",
    "architecture.md",
    "data-model.md",
    "roles-and-permissions.md",
    "scheduling-engine.md",
    "evaluation-and-analytics.md",
    "data-import.md",
    "api-reference.md",
    "frontend.md",
    "operations.md",
    "faq.md",
    "glossary.md",
    "roadmap.md",
]

# Chapter titles, used to turn a cross-file link into a readable reference.
TITLES = {
    "README.md": "Overview",
    "architecture.md": "Architecture",
    "data-model.md": "Data model",
    "roles-and-permissions.md": "Roles and permissions",
    "scheduling-engine.md": "The scheduling engine",
    "evaluation-and-analytics.md": "Evaluation and analytics",
    "data-import.md": "Data import",
    "api-reference.md": "API reference",
    "frontend.md": "Frontend",
    "operations.md": "Running, configuring and testing",
    "faq.md": "FAQ",
    "glossary.md": "Glossary",
    "roadmap.md": "Roadmap",
}

PAGE_BREAK = '\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n'

META = f"""---
title: "AcademiSync"
subtitle: "Automated Interview Scheduling and Evaluation Management System — Technical Documentation"
date: "{date.today():%d %B %Y}"
lang: en-GB
---

"""


def resolve_links(text: str) -> str:
    """`[x](architecture.md#error-model)` -> `x (see "Architecture")`."""

    def repl(match: re.Match) -> str:
        label, target = match.group(1), match.group(2)
        if target.startswith("http") or target.startswith("#"):
            return match.group(0)
        name = target.split("#")[0].split("/")[-1]
        chapter = TITLES.get(name)
        if chapter is None:
            return label
        if label.strip().lower() in (name.lower(), chapter.lower()):
            # "the "The scheduling engine" chapter" reads badly.
            return f'the "{chapter.removeprefix("The ")}" chapter'
        return f'{label} (see "{chapter}")'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", repl, text)


def drop_section(text: str, heading: str) -> str:
    """Remove a `## heading` block - the index table is redundant in Word."""
    pattern = rf"^## {re.escape(heading)}\n.*?(?=^## )"
    return re.sub(pattern, "", text, flags=re.S | re.M)


SEPARATOR = re.compile(r"^\s*\|[\s|-]+\|\s*$")


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def visual_length(cell: str) -> int:
    """Character count, weighting code spans for their wider monospace font."""
    code = sum(len(part) for part in re.findall(r"`([^`]*)`", cell))
    return round(len(cell) - code + code * 1.2)


def size_columns(text: str) -> str:
    """Rewrite table separators so their dash runs are proportional.

    Pandoc takes a pipe table's relative column widths from the width of the
    dashes in its separator line.  Hand-written separators are all roughly the
    same length, which lands every column at the same width in Word - wrapping
    `/faculty-availability` over three lines next to a half-empty "Access"
    column.  Sizing the dashes to the widest cell fixes every table at once,
    and Markdown itself ignores the dash count, so the sources stay readable.
    """
    lines = text.split("\n")
    out = list(lines)
    index = 1
    while index < len(lines):
        if not (SEPARATOR.match(lines[index]) and "|" in lines[index - 1]):
            index += 1
            continue
        end = index + 1
        while end < len(lines) and lines[end].strip().startswith("|"):
            end += 1
        rows = [split_row(lines[i]) for i in range(index - 1, end) if i != index]

        count = len(split_row(lines[index]))
        widths = []
        for column in range(count):
            longest = max((visual_length(row[column]) for row in rows
                           if column < len(row)),
                          default=3)
            # Cap the widest column and give every column a constant of
            # padding, so a narrow one keeps enough share for "DELETE" not to
            # wrap while a prose column stops crowding it out.
            widths.append(min(max(longest, 8), 40) + 6)
        out[index] = "| " + " | ".join("-" * w for w in widths) + " |"
        index = end
    return "\n".join(out)


def chapter_text(name: str) -> str:
    text = (DOCS / name).read_text()
    if name == "README.md":
        text = drop_section(text, "Where to start")
        # The standalone index title reads oddly as a chapter heading.
        text = text.replace("# AcademiSync — Documentation", "# Overview", 1)
    return size_columns(resolve_links(text))


def contents(chapters: list[tuple[str, str]]) -> str:
    """A contents table written into the document as ordinary content.

    Pandoc's `--toc` emits a Word TOC *field*, which renders as an empty box
    until the reader updates it - and shows nothing at all in Preview, Google
    Docs or LibreOffice.  A plain table always renders; Word's navigation pane
    still works from the heading styles either way.
    """
    rows = ["# Contents", "", "| Chapter | Sections |", "| --- | --- |"]
    for title, text in chapters:
        sections = re.findall(r"^## (.+)$", text, flags=re.M)
        rows.append(f"| **{title}** | {' · '.join(sections)} |")
    return size_columns("\n".join(rows)) + "\n"


def build() -> str:
    chapters = [(TITLES[name], chapter_text(name)) for name in CHAPTERS]
    parts = [META, contents(chapters), PAGE_BREAK]
    for index, (_, text) in enumerate(chapters):
        if index:
            parts.append(PAGE_BREAK)
        parts.append(text.rstrip() + "\n")
    return "\n".join(parts)


def main() -> int:
    combined = DOCS / ".combined.md"
    combined.write_text(build())
    try:
        subprocess.run(
            ["pandoc", str(combined), "--from", "markdown", "--to", "docx",
             "--standalone", "--output", str(OUTPUT)],
            check=True)
    except FileNotFoundError:
        print("pandoc is not installed - `brew install pandoc`", file=sys.stderr)
        return 1
    finally:
        combined.unlink(missing_ok=True)
    print(f"Wrote {OUTPUT.relative_to(DOCS.parent)} "
          f"({OUTPUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
