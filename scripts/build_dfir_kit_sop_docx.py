#!/usr/bin/env python3
"""Merge DFIR-Kit-Deployment markdown guides into one DOCX via Pandoc."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FOOTER_SPLIT = "\n---\n\n## DFIR kit guides\n"
YAML_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL | re.MULTILINE)

GUIDE_DIR = Path(__file__).resolve().parent.parent / "Documents" / "Guides" / "DFIR-Kit-Deployment"
ORDERED_FILES = [
    "index.md",
    "01_Introduction.md",
    "02_Limitations.md",
    "03_ESXi-Deployment.md",
    "04_NAS-Deployment.md",
    "05_ELK-Deployment.md",
    "06_Flare-VM-Build.md",
    "07_Artifact-Carving.md",
    "08_Suggestions.md",
    "Plaso_JSONL_Extraction_Guide.md",
]
OUT_MD = GUIDE_DIR / "_DFIR_Kit_SOP_combined.md"
OUT_DOCX = GUIDE_DIR / "DFIR_Kit_SOP.docx"


def strip_yaml(text: str) -> str:
    return YAML_RE.sub("", text, count=1)


def strip_footer(text: str) -> str:
    if FOOTER_SPLIT in text:
        text = text.rsplit(FOOTER_SPLIT, 1)[0]
    return text.rstrip()


def extract_title(text: str) -> str | None:
    m = re.search(r"^title:\s*(.+)\s*$", text, re.MULTILINE)
    if not m:
        return None
    raw = m.group(1).strip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def main() -> int:
    pandoc = Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe"
    if not pandoc.is_file():
        print("Pandoc not found at", pandoc, file=sys.stderr)
        return 1

    parts: list[str] = []
    parts.append(
        "---\n"
        "title: DFIR Kit Deployment SOP\n"
        "subtitle: Standalone ESXi Lab | NAS | FLARE VM | ELK Stack\n"
        "author: Nicolas A. Welsh\n"
        "lang: en-US\n"
        "---\n\n"
    )

    for name in ORDERED_FILES:
        path = GUIDE_DIR / name
        raw = path.read_text(encoding="utf-8")
        title = extract_title(raw)
        body = strip_footer(strip_yaml(raw)).rstrip()
        if name != "index.md":
            label = title or name.replace(".md", "").replace("_", " ")
            parts.append(f"\n\n# {label}\n\n")
        parts.append(body)
        parts.append("\n\n")

    combined = "".join(parts).rstrip() + "\n"
    OUT_MD.write_text(combined, encoding="utf-8")

    cmd = [
        str(pandoc),
        str(OUT_MD),
        "-o",
        str(OUT_DOCX),
        "-s",
        "--toc",
        "--toc-depth=4",
        "--standalone",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    OUT_MD.unlink(missing_ok=True)
    print("Wrote", OUT_DOCX)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
