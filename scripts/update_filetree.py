#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "Content"
FILETREE_PATH = ROOT / "Filetree.json"
README_PATH = ROOT / "README.md"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def is_zero_sha(value: str | None) -> bool:
    return bool(value) and set(value) == {"0"}


def is_content_image(path: str) -> bool:
    parts = Path(path).parts
    return (
        len(parts) >= 3
        and parts[0] == "Content"
        and Path(path).suffix.lower() in IMAGE_EXTENSIONS
    )


def run_git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout


def changed_paths_from_git(changed_from: str | None, changed_to: str | None) -> set[str]:
    if changed_from and changed_to:
        if is_zero_sha(changed_from):
            args = [
                "diff-tree",
                "--no-commit-id",
                "--name-status",
                "--find-renames",
                "-r",
                changed_to,
                "--",
                "Content",
            ]
        else:
            args = [
                "diff",
                "--name-status",
                "--find-renames",
                changed_from,
                changed_to,
                "--",
                "Content",
            ]
    else:
        args = [
            "diff",
            "--cached",
            "--name-status",
            "--find-renames",
            "--",
            "Content",
        ]

    try:
        output = run_git(args)
    except subprocess.CalledProcessError:
        output = run_git(
            [
                "diff-tree",
                "--no-commit-id",
                "--name-status",
                "--find-renames",
                "-r",
                changed_to or "HEAD",
                "--",
                "Content",
            ]
        )

    paths: set[str] = set()
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0]
        if status.startswith("R") or status.startswith("C"):
            candidates = fields[1:3]
        else:
            candidates = fields[1:2]
        for candidate in candidates:
            if is_content_image(candidate):
                paths.add(candidate)
    return paths


def split_content_path(path: str) -> tuple[str, str]:
    parts = Path(path).parts
    return parts[1], "/".join(parts[2:])


def split_current_image_path(path: Path) -> tuple[str, str]:
    relative = path.relative_to(CONTENT_DIR)
    parts = relative.parts
    if len(parts) < 2:
        raise ValueError(f"{path} is not under a Content subdirectory")
    return parts[0], "/".join(parts[1:])


def strip_query(value: str) -> str:
    return value.split("?t=", 1)[0]


def with_timestamp(target: str, timestamp: int) -> str:
    return f"{target}?t={timestamp}"


def load_filetree() -> dict:
    if not FILETREE_PATH.exists():
        return {"Content": {}, "Information": {}}
    with FILETREE_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    data.setdefault("Content", {})
    data.setdefault("Information", {})
    return data


def iter_current_images() -> Iterable[Path]:
    if not CONTENT_DIR.exists():
        return
    for path in CONTENT_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def current_image_stats() -> tuple[int, int]:
    total_num = 0
    total_size = 0
    for path in iter_current_images():
        total_num += 1
        total_size += path.stat().st_size
    return total_num, total_size


def current_image_snapshot() -> tuple[dict[str, set[str]], int, int]:
    images: dict[str, set[str]] = {}
    total_num = 0
    total_size = 0

    for path in iter_current_images():
        total_num += 1
        total_size += path.stat().st_size
        try:
            company, target = split_current_image_path(path)
        except ValueError:
            continue
        images.setdefault(company, set()).add(target)

    return images, total_num, total_size


def badge_date(timestamp: object) -> str:
    try:
        value = float(timestamp)
    except (TypeError, ValueError):
        value = time.time()
    date = datetime.fromtimestamp(value, timezone.utc)
    return f"{date.year}--{date.month}--{date.day}"


def update_readme_badges(info: dict[str, object]) -> bool:
    if not README_PATH.exists():
        return False

    total_num = int(info.get("TotalNum", 0))
    total_badge = f"全部女友数-{total_num:,}-blueviolet.svg"
    date_badge = f"更新日期-{badge_date(info.get('Timestamp'))}-brightgreen.svg"

    readme = README_PATH.read_text(encoding="utf-8")
    updated = re.sub(
        r"(?:TotalNum|全部女友数)-[0-9,]+-blueviolet\.svg",
        total_badge,
        readme,
        count=1,
    )
    updated = re.sub(
        r"(?:AutoUpdate|更新日期)-\d{4}--\d{1,2}--\d{1,2}-brightgreen\.svg",
        date_badge,
        updated,
        count=1,
    )

    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
        print("Updated README.md badges.")
        return True
    return False


def display_key_for_target(entries: dict[str, str], target: str) -> str | None:
    target_name = Path(target).name
    if target_name.startswith("AI-Fix-"):
        preferred = target_name.removeprefix("AI-Fix-")
    else:
        preferred = target

    if preferred not in entries or strip_query(entries[preferred]) == target:
        return preferred
    if target not in entries or strip_query(entries[target]) == target:
        return target
    return None


def update_filetree(changed_paths: set[str]) -> bool:
    data = load_filetree()

    if not changed_paths:
        print("No changed Content images; Filetree.json unchanged.")
        return update_readme_badges(data.get("Information", {}))

    content = data["Content"]
    run_timestamp = time.time()
    file_timestamp = int(run_timestamp)
    changed = False

    for changed_path in sorted(changed_paths):
        company, target = split_content_path(changed_path)
        target_path = CONTENT_DIR / company / target
        entries = content.setdefault(company, {})

        if target_path.exists():
            new_value = with_timestamp(target, file_timestamp)
            touched_existing = False
            for key, value in list(entries.items()):
                if strip_query(value) == target:
                    touched_existing = True
                    if value != new_value:
                        entries[key] = new_value
                        changed = True
            if not touched_existing:
                key = display_key_for_target(entries, target)
                if key is None:
                    print(f"Skipped {changed_path}: no non-conflicting Filetree key.")
                    continue
                entries[key] = new_value
                changed = True
        else:
            for key, value in list(entries.items()):
                if strip_query(value) == target:
                    del entries[key]
                    changed = True
            if not entries:
                del content[company]

    if changed:
        total_num, total_size = current_image_stats()
        data["Information"] = {
            "TotalNum": str(total_num),
            "TotalSize": str(total_size),
            "Timestamp": run_timestamp,
        }
        data["Content"] = {
            company: content[company] for company in sorted(content.keys(), reverse=True)
        }
        rendered = json.dumps(data, ensure_ascii=False, indent=1)
        existing = (
            FILETREE_PATH.read_text(encoding="utf-8") if FILETREE_PATH.exists() else ""
        )
        if rendered != existing:
            FILETREE_PATH.write_text(rendered, encoding="utf-8")
            print(f"Updated Filetree.json from {len(changed_paths)} changed image(s).")
            update_readme_badges(data["Information"])
            return True

    print("Changed images did not alter Filetree.json.")
    return update_readme_badges(data.get("Information", {}))


def print_skipped_summary(skipped: list[str], verbose: bool) -> None:
    if not skipped:
        return

    print(
        "Skipped "
        f"{len(skipped)} image(s) whose natural Filetree key already points "
        "to another image."
    )
    if verbose:
        for path in skipped:
            print(f"Skipped {path}: no non-conflicting Filetree key.")
    else:
        sample = ", ".join(skipped[:5])
        print(f"Examples: {sample}")
        print("Run again with --verbose to print every skipped path.")


def sync_full_filetree(refresh_timestamps: bool = False, verbose: bool = False) -> bool:
    data = load_filetree()
    content = data["Content"]
    images, total_num, total_size = current_image_snapshot()
    run_timestamp = time.time()
    file_timestamp = int(run_timestamp)
    next_content: dict[str, dict[str, str]] = {}
    skipped: list[str] = []

    for company in sorted(images.keys(), reverse=True):
        targets = images[company]
        existing_entries = content.get(company, {})
        next_entries: dict[str, str] = {}
        covered_targets: set[str] = set()

        for key, value in existing_entries.items():
            target = strip_query(value)
            if target not in targets:
                continue

            covered_targets.add(target)
            next_value = value
            if refresh_timestamps or "?t=" not in value:
                next_value = with_timestamp(target, file_timestamp)
            next_entries[key] = next_value

        for target in sorted(targets - covered_targets):
            key = display_key_for_target(next_entries, target)
            if key is None:
                skipped.append(f"Content/{company}/{target}")
                continue
            next_entries[key] = with_timestamp(target, file_timestamp)

        if next_entries:
            next_content[company] = next_entries

    old_info = data.get("Information", {})
    old_total_num = str(old_info.get("TotalNum", ""))
    old_total_size = str(old_info.get("TotalSize", ""))
    content_changed = next_content != content
    info_changed = old_total_num != str(total_num) or old_total_size != str(total_size)

    if content_changed or info_changed or refresh_timestamps:
        data["Information"] = {
            "TotalNum": str(total_num),
            "TotalSize": str(total_size),
            "Timestamp": run_timestamp,
        }
    else:
        data["Information"] = old_info
    data["Content"] = next_content

    print_skipped_summary(skipped, verbose)

    rendered = json.dumps(data, ensure_ascii=False, indent=1)
    existing = FILETREE_PATH.read_text(encoding="utf-8") if FILETREE_PATH.exists() else ""
    if rendered != existing:
        FILETREE_PATH.write_text(rendered, encoding="utf-8")
        print("Updated Filetree.json from local Content scan.")
        update_readme_badges(data["Information"])
        return True

    print("Filetree.json is already up to date.")
    return update_readme_badges(data.get("Information", {}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Filetree.json for changed images.")
    parser.add_argument(
        "--all",
        "--full-scan",
        action="store_true",
        dest="full_scan",
        help="Scan every image under Content for local Filetree.json updates.",
    )
    parser.add_argument("--changed-from", help="Base git revision for changed files.")
    parser.add_argument("--changed-to", help="Head git revision for changed files.")
    parser.add_argument(
        "--refresh-timestamps",
        action="store_true",
        help="With --all, refresh every Filetree ?t= cache timestamp.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every skipped path during a full local scan.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.full_scan:
        sync_full_filetree(
            refresh_timestamps=args.refresh_timestamps,
            verbose=args.verbose,
        )
        return 0
    if args.refresh_timestamps:
        raise SystemExit("--refresh-timestamps requires --all or --full-scan.")
    changed_paths = changed_paths_from_git(args.changed_from, args.changed_to)
    update_filetree(changed_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
