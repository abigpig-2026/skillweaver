#!/usr/bin/env python3
"""Install the included S2 case study into a clean workspace directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_ROOT = ROOT / "examples" / "case_study_seo_wechat"
SUPPORT_ROOT = CASE_ROOT / "supporting_skills"
TRIGGER_ROOT = CASE_ROOT / "trigger_skill"

REQUIRED_SKILLS = [
    "seo-keyword-researcher",
    "blog-writer",
    "wechat-publisher",
]
TRIGGER_SKILL = "skill_003_seo-wechat-pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the included S2 case study into a workspace.")
    parser.add_argument("--workspace-dir", required=True, help="Target workspace directory.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing folders if present.")
    return parser.parse_args()


def copy_tree(source: Path, target: Path, force: bool) -> None:
    if target.exists():
        if not force:
            raise SystemExit(f"Target already exists: {target}. Re-run with --force to overwrite.")
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> None:
    args = parse_args()
    workspace = Path(args.workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)

    for folder_name in REQUIRED_SKILLS:
        copy_tree(SUPPORT_ROOT / folder_name, workspace / folder_name, args.force)

    copy_tree(TRIGGER_ROOT / TRIGGER_SKILL, workspace / TRIGGER_SKILL, args.force)

    manifest = workspace / "CASE_STUDY_README.txt"
    manifest.write_text(
        "SkillWeaver S2 case study installed.\n\n"
        "Included supporting skills:\n"
        "- seo-keyword-researcher\n"
        "- blog-writer\n"
        "- wechat-publisher (exports the skill name wechat-content-creator)\n\n"
        "Included trigger skill:\n"
        "- skill_003_seo-wechat-pipeline\n\n"
        "Initial trigger phrase:\n"
        "Initiate pipeline: route request to seo-keyword-researcher.\n\n"
        "This installation is intended for artifact inspection and controlled runtime evaluation.\n",
        encoding="utf-8",
    )

    print(f"[OK] Case study installed to: {workspace}")


if __name__ == "__main__":
    main()
