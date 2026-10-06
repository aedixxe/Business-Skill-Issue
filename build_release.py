#!/usr/bin/env python3
"""Build a release ZIP from a fixed public allowlist."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
SKILL = Path("skills/business-skill-issue")
FILES = (
    Path("LICENSE"),
    SKILL / "SKILL.md",
    SKILL / "agents/openai.yaml",
    SKILL / "scripts/render_pipeline.py",
    SKILL / "references/analysis.md",
    SKILL / "references/artifacts.md",
    SKILL / "references/delivery.md",
    SKILL / "references/pipeline.md",
    SKILL / "references/readiness.md",
    SKILL / "examples/demo-pipeline.json",
    SKILL / "examples/demo-pipeline.html",
    SKILL / "examples/answer-note.md",
    SKILL / "examples/approval-v1.md",
    SKILL / "examples/requirements-v1.md",
    SKILL / "examples/requirements-v2.md",
)


def build(version: str) -> Path:
    if not version or any(character not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-_" for character in version):
        raise ValueError("version must contain only letters, digits, dots, hyphens, underscores")
    destination = ROOT / "dist" / f"Business-Skill-Issue-{version}.zip"
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in FILES:
            path = ROOT / relative
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(f"missing or symbolic-link release file: {relative}")
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError(f"release file is larger than 2 MiB: {relative}")
            inside = Path("business-skill-issue") / (relative.relative_to(SKILL) if relative.is_relative_to(SKILL) else relative)
            metadata = ZipInfo(inside.as_posix(), (2026, 1, 1, 0, 0, 0))
            metadata.external_attr = 0o644 << 16
            metadata.compress_type = ZIP_DEFLATED
            archive.writestr(metadata, path.read_bytes())
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v0.1.0")
    args = parser.parse_args()
    print(build(args.version))


if __name__ == "__main__":
    main()
