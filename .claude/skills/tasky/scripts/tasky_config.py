#!/usr/bin/env python3
"""
tasky_config.py — Reads Nimbility configuration from nimbility.md at repo root.

Exported:
    NIMBILITY_ROOT  — absolute path to the project data directory
"""

import os
import re
import sys


_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def _find_repo_root():
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(current, "nimbility.md")):
            return current
        if os.path.isdir(os.path.join(current, ".git")):
            return current

        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _find_root():
    repo_root = _find_repo_root()
    default_root = os.path.abspath(
        os.path.join(repo_root, "agents", "nimbility")
    ) if repo_root else os.path.abspath(os.path.join("agents", "nimbility"))

    if not repo_root:
        return default_root

    config_file = os.path.join(repo_root, "nimbility.md")
    if os.path.isfile(config_file):
        with open(config_file) as f:
            for line in f:
                m = re.match(r"^root:\s*(.+)$", line.strip())
                if m:
                    configured_root = m.group(1).strip()
                    if configured_root:
                        return os.path.abspath(os.path.join(repo_root, configured_root))

    return default_root


def validate_slug(slug, label="slug"):
    if not slug or not _SLUG_RE.fullmatch(slug):
        print(
            f"Error: invalid {label} '{slug}'. Only lowercase letters, numbers, and hyphens are allowed.",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_slash_path(value, parts, label="path"):
    items = value.split("/")
    if len(items) != parts:
        print(f"Error: invalid {label} '{value}'. Expected {parts} slash-separated slug parts.", file=sys.stderr)
        sys.exit(1)
    for idx, item in enumerate(items, start=1):
        validate_slug(item, f"{label} part {idx}")
    return items


NIMBILITY_ROOT = _find_root()
