#!/usr/bin/env python3
"""
manage_projects.py — Create and manage projects.

Usage:
  python manage_projects.py create-project <slug>
  python manage_projects.py rename-project <slug> <new-slug>
  python manage_projects.py delete-project <slug>
  python manage_projects.py list
"""

import os
import sys
import json
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT, validate_slug


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def project_path(project):
    return os.path.join(NIMBILITY_ROOT, project)

def project_json_path(project):
    return os.path.join(project_path(project), "project.json")

def assert_not_exists(path, label):
    if os.path.exists(path):
        print(f"Error: {label} already exists at {path}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create_project(args):
    slug = args.slug
    validate_slug(slug, "project slug")
    path = project_path(slug)
    assert_not_exists(path, f"project '{slug}'")

    os.makedirs(path)

    pj = {
        "roadmaps": [], "tracks": {}, "milestones": {}, "tasks": {},
        "oob_roadmaps": {}, "oob_tracks": {}, "oob_milestones": {}, "oob_tasks": {},
        "milestone_deps": {}, "milestone_slots": {}, "track_slots": {},
    }
    with open(project_json_path(slug), "w") as f:
        json.dump(pj, f, indent=2)

    print(f"Created project: {path}")
    print(f"Created: {project_json_path(slug)}")


def cmd_rename_project(args):
    validate_slug(args.slug, "project slug")
    validate_slug(args.new_slug, "new project slug")
    old_path = project_path(args.slug)
    new_path = project_path(args.new_slug)
    if not os.path.isdir(old_path):
        print(f"Error: project '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)
    assert_not_exists(new_path, f"project '{args.new_slug}'")
    os.rename(old_path, new_path)
    print(f"Renamed project '{args.slug}' → '{args.new_slug}'")


def cmd_delete_project(args):
    validate_slug(args.slug, "project slug")
    path = project_path(args.slug)
    if not os.path.isdir(path):
        print(f"Error: project '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)
    shutil.rmtree(path)
    print(f"Deleted project: {path}")


def cmd_list(args):
    if not os.path.isdir(NIMBILITY_ROOT):
        print("No projects found.")
        return

    for project_name in sorted(os.listdir(NIMBILITY_ROOT)):
        p = os.path.join(NIMBILITY_ROOT, project_name)
        if not os.path.isdir(p) or project_name.startswith("."):
            continue
        print(f"project: {project_name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage nimbility projects.")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create-project", help="Create a new project")
    p_create.add_argument("slug", help="Project slug (e.g. studio)")

    p_rename = sub.add_parser("rename-project", help="Rename a project")
    p_rename.add_argument("slug")
    p_rename.add_argument("new_slug")

    p_delete = sub.add_parser("delete-project", help="Delete a project and all its contents")
    p_delete.add_argument("slug")

    sub.add_parser("list", help="List all projects")

    args = parser.parse_args()

    if args.command == "create-project":
        cmd_create_project(args)
    elif args.command == "rename-project":
        cmd_rename_project(args)
    elif args.command == "delete-project":
        cmd_delete_project(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
