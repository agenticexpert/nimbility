#!/usr/bin/env python3
"""
manage_roadmaps.py — Create and manage roadmaps within a project.

Usage:
  python manage_roadmaps.py create <project> <slug> [--oob]
  python manage_roadmaps.py rename <project> <slug> <new-slug>
  python manage_roadmaps.py delete <project> <slug>
  python manage_roadmaps.py move <project> <roadmap> --dest <project> [--insert <n>]
  python manage_roadmaps.py hide <project> <slug>
  python manage_roadmaps.py unhide <project> <slug>
  python manage_roadmaps.py list [<project>]
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

def roadmap_path(project, roadmap):
    return os.path.join(NIMBILITY_ROOT, project, roadmap)

def project_json_path(project):
    return os.path.join(project_path(project), "project.json")

def load_project_json(project):
    path = project_json_path(project)
    if not os.path.exists(path):
        return {"roadmaps": [], "tracks": {}, "milestones": {}, "tasks": {}}
    with open(path) as f:
        data = json.load(f)
    data.setdefault("roadmaps", [])
    data.setdefault("tracks", {})
    data.setdefault("milestones", {})
    data.setdefault("tasks", {})
    data.setdefault("oob_roadmaps", {})
    data.setdefault("oob_tracks", {})
    data.setdefault("oob_milestones", {})
    data.setdefault("oob_tasks", {})
    data.setdefault("milestone_deps", {})
    return data

def save_project_json(project, data):
    with open(project_json_path(project), "w") as f:
        json.dump(data, f, indent=2)

def assert_project_exists(project):
    p = project_path(project)
    if not os.path.isdir(p):
        print(f"Error: project '{project}' does not exist at {p}", file=sys.stderr)
        sys.exit(1)

def assert_not_exists(path, label):
    if os.path.exists(path):
        print(f"Error: {label} already exists at {path}", file=sys.stderr)
        sys.exit(1)

def focus_hide_add(data, slug):
    hide = data.setdefault("focus", {}).setdefault("hide", {})
    lst = hide.setdefault("roadmaps", [])
    if slug not in lst:
        lst.append(slug)

def focus_hide_remove(data, slug):
    hide = data.get("focus", {}).get("hide", {})
    if not hide:
        return
    lst = hide.get("roadmaps", [])
    if slug in lst:
        lst.remove(slug)
    if not lst:
        hide.pop("roadmaps", None)
    if not hide:
        data.get("focus", {}).pop("hide", None)
    if not data.get("focus", {}):
        data.pop("focus", None)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.slug, "roadmap slug")
    assert_project_exists(args.project)
    path = roadmap_path(args.project, args.slug)
    assert_not_exists(path, f"roadmap '{args.slug}'")

    os.makedirs(path)

    data = load_project_json(args.project)
    if args.oob:
        oob_list = data.setdefault("oob_roadmaps", {}).setdefault(args.project, [])
        if args.slug not in oob_list:
            oob_list.append(args.slug)
    else:
        if args.slug not in data["roadmaps"]:
            data["roadmaps"].append(args.slug)
    save_project_json(args.project, data)

    print(f"Created roadmap: {path}")


def cmd_rename(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.slug, "roadmap slug")
    validate_slug(args.new_slug, "new roadmap slug")
    assert_project_exists(args.project)
    old_path = roadmap_path(args.project, args.slug)
    new_path = roadmap_path(args.project, args.new_slug)
    if not os.path.isdir(old_path):
        print(f"Error: roadmap '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)
    assert_not_exists(new_path, f"roadmap '{args.new_slug}'")
    os.rename(old_path, new_path)

    data = load_project_json(args.project)

    # Update roadmaps list
    if args.slug in data["roadmaps"]:
        idx = data["roadmaps"].index(args.slug)
        data["roadmaps"][idx] = args.new_slug

    # Update oob_roadmaps list
    oob_list = data.get("oob_roadmaps", {}).get(args.project, [])
    if args.slug in oob_list:
        oob_list[oob_list.index(args.slug)] = args.new_slug

    # Update tracks keys
    old_tracks = data["tracks"].pop(args.slug, None)
    if old_tracks is not None:
        data["tracks"][args.new_slug] = old_tracks

    # Update all prefix-keyed mappings
    old_prefix = args.slug + "/"
    new_prefix = args.new_slug + "/"
    for mapping in (data["milestones"], data["oob_milestones"], data["tasks"],
                    data["oob_tasks"], data["milestone_deps"]):
        for key in list(mapping.keys()):
            if key.startswith(old_prefix):
                mapping[new_prefix + key[len(old_prefix):]] = mapping.pop(key)

    # Update oob_tracks key
    if args.slug in data["oob_tracks"]:
        data["oob_tracks"][args.new_slug] = data["oob_tracks"].pop(args.slug)

    # Update focus.hide references
    hide = data.get("focus", {}).get("hide", {})
    if hide:
        # roadmaps list
        rm_list = hide.get("roadmaps", [])
        if args.slug in rm_list:
            rm_list[rm_list.index(args.slug)] = args.new_slug
        # tracks dict key
        if args.slug in hide.get("tracks", {}):
            hide["tracks"][args.new_slug] = hide["tracks"].pop(args.slug)
        # milestones dict keys with old roadmap prefix
        for key in list(hide.get("milestones", {}).keys()):
            if key.startswith(old_prefix):
                hide["milestones"][new_prefix + key[len(old_prefix):]] = hide["milestones"].pop(key)

    save_project_json(args.project, data)
    print(f"Renamed roadmap '{args.slug}' → '{args.new_slug}'")


def cmd_delete(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.slug, "roadmap slug")
    assert_project_exists(args.project)
    path = roadmap_path(args.project, args.slug)
    if not os.path.isdir(path):
        print(f"Error: roadmap '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)
    shutil.rmtree(path)

    data = load_project_json(args.project)

    data["roadmaps"] = [r for r in data["roadmaps"] if r != args.slug]
    oob_list = data.get("oob_roadmaps", {}).get(args.project, [])
    data.setdefault("oob_roadmaps", {})[args.project] = [r for r in oob_list if r != args.slug]

    data["tracks"].pop(args.slug, None)
    data["oob_tracks"].pop(args.slug, None)

    prefix = args.slug + "/"
    for mapping in (data["milestones"], data["oob_milestones"], data["tasks"],
                    data["oob_tasks"], data["milestone_deps"]):
        for key in list(mapping.keys()):
            if key.startswith(prefix):
                del mapping[key]

    # Clean up focus.hide references
    hide = data.get("focus", {}).get("hide", {})
    if hide:
        rm_list = hide.get("roadmaps", [])
        if args.slug in rm_list:
            rm_list.remove(args.slug)
        hide.get("tracks", {}).pop(args.slug, None)
        for key in list(hide.get("milestones", {}).keys()):
            if key.startswith(prefix):
                del hide["milestones"][key]

    save_project_json(args.project, data)
    print(f"Deleted roadmap: {path}")


def cmd_move(args):
    src_project = args.project
    roadmap = args.roadmap
    dest_project = args.dest

    validate_slug(src_project, "source project slug")
    validate_slug(roadmap, "roadmap slug")
    validate_slug(dest_project, "destination project slug")

    assert_project_exists(src_project)
    assert_project_exists(dest_project)

    src_rmap_path = roadmap_path(src_project, roadmap)
    if not os.path.isdir(src_rmap_path):
        print(f"Error: roadmap '{roadmap}' does not exist in project '{src_project}'.", file=sys.stderr)
        sys.exit(1)

    dst_rmap_path = roadmap_path(dest_project, roadmap)
    if os.path.exists(dst_rmap_path):
        print(f"Error: roadmap '{roadmap}' already exists in destination project '{dest_project}'.", file=sys.stderr)
        sys.exit(1)

    src_data = load_project_json(src_project)
    dst_data = load_project_json(dest_project)

    prefix = roadmap + "/"

    src_tracks_entry = src_data["tracks"].get(roadmap)
    src_oob_tracks   = roadmap in src_data.get("oob_tracks", {})
    src_milestones   = {k: v for k, v in src_data["milestones"].items()     if k.startswith(prefix)}
    src_oob_miles    = {k: v for k, v in src_data["oob_milestones"].items() if k.startswith(prefix)}
    src_tasks        = {k: v for k, v in src_data["tasks"].items()           if k.startswith(prefix)}
    src_oob_tasks    = {k: v for k, v in src_data["oob_tasks"].items()       if k.startswith(prefix)}
    src_ms_deps      = {k: v for k, v in src_data["milestone_deps"].items()  if k.startswith(prefix)}

    shutil.move(src_rmap_path, dst_rmap_path)

    src_is_oob = roadmap in src_data.get("oob_roadmaps", {}).get(src_project, [])

    # Remove from source
    src_data["roadmaps"] = [r for r in src_data["roadmaps"] if r != roadmap]
    src_oob_list = src_data.get("oob_roadmaps", {}).get(src_project, [])
    src_data.setdefault("oob_roadmaps", {})[src_project] = [r for r in src_oob_list if r != roadmap]
    src_data["tracks"].pop(roadmap, None)
    src_data["oob_tracks"].pop(roadmap, None)
    for mapping in (src_data["milestones"], src_data["oob_milestones"], src_data["tasks"],
                    src_data["oob_tasks"], src_data["milestone_deps"]):
        for key in list(mapping.keys()):
            if key.startswith(prefix):
                del mapping[key]

    # Add to destination
    if src_is_oob:
        oob_list = dst_data.setdefault("oob_roadmaps", {}).setdefault(dest_project, [])
        if roadmap not in oob_list:
            oob_list.append(roadmap)
    elif args.insert:
        insert_at = max(1, min(args.insert, len(dst_data["roadmaps"]) + 1)) - 1
        dst_data["roadmaps"].insert(insert_at, roadmap)
    else:
        if roadmap not in dst_data["roadmaps"]:
            dst_data["roadmaps"].append(roadmap)

    if src_tracks_entry is not None:
        dst_data["tracks"][roadmap] = src_tracks_entry
    if src_oob_tracks:
        dst_data["oob_tracks"].setdefault(roadmap, [])

    dst_data["milestones"].update(src_milestones)
    dst_data["oob_milestones"].update(src_oob_miles)
    dst_data["tasks"].update(src_tasks)
    dst_data["oob_tasks"].update(src_oob_tasks)
    dst_data["milestone_deps"].update(src_ms_deps)

    save_project_json(src_project, src_data)
    save_project_json(dest_project, dst_data)
    print(f"Moved roadmap '{roadmap}' from project '{src_project}' to project '{dest_project}'.")


def cmd_hide(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.slug, "roadmap slug")
    assert_project_exists(args.project)
    path = roadmap_path(args.project, args.slug)
    if not os.path.isdir(path):
        print(f"Error: roadmap '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)

    data = load_project_json(args.project)

    oob_list = data.get("oob_roadmaps", {}).get(args.project, [])
    if args.slug in oob_list:
        print(f"Error: OOB roadmaps cannot be hidden.", file=sys.stderr)
        sys.exit(1)

    focus_hide_add(data, args.slug)
    save_project_json(args.project, data)
    print(f"Hidden roadmap '{args.slug}' — excluded from default views. Use --all to reveal.")


def cmd_unhide(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.slug, "roadmap slug")
    assert_project_exists(args.project)
    data = load_project_json(args.project)
    focus_hide_remove(data, args.slug)
    save_project_json(args.project, data)
    print(f"Roadmap '{args.slug}' restored to focus.")


def cmd_list(args):
    if args.project:
        validate_slug(args.project, "project slug")
        projects = [args.project]
    else:
        if not os.path.isdir(NIMBILITY_ROOT):
            print("No projects found.")
            return
        projects = sorted([
            d for d in os.listdir(NIMBILITY_ROOT)
            if os.path.isdir(os.path.join(NIMBILITY_ROOT, d)) and not d.startswith(".")
        ])

    for project_name in projects:
        project_dir = os.path.join(NIMBILITY_ROOT, project_name)
        if not os.path.isdir(project_dir):
            print(f"Error: project '{project_name}' does not exist.", file=sys.stderr)
            continue

        data = load_project_json(project_name)
        roadmap_order = data.get("roadmaps", [])
        oob_set = set(data.get("oob_roadmaps", {}).get(project_name, []))
        hidden_set = set(data.get("focus", {}).get("hide", {}).get("roadmaps", []))

        fs_roadmaps = sorted([
            d for d in os.listdir(project_dir)
            if os.path.isdir(os.path.join(project_dir, d)) and not d.startswith(".")
        ])
        ordered = roadmap_order + [r for r in fs_roadmaps if r not in roadmap_order and r not in oob_set]

        print(f"project: {project_name}")
        for rname in ordered:
            r = os.path.join(project_dir, rname)
            if os.path.isdir(r):
                suffix = "  ~" if rname in hidden_set else ""
                print(f"  roadmap: {rname}{suffix}")
        for rname in sorted(oob_set):
            r = os.path.join(project_dir, rname)
            if os.path.isdir(r):
                print(f"  · roadmap: {rname}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage nimbility roadmaps.")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Create a roadmap under a project")
    p_create.add_argument("project", help="Project slug")
    p_create.add_argument("slug", help="Roadmap slug")
    p_create.add_argument("--oob", action="store_true", help="Mark as out-of-band (not in sequence)")

    p_rename = sub.add_parser("rename", help="Rename a roadmap")
    p_rename.add_argument("project")
    p_rename.add_argument("slug")
    p_rename.add_argument("new_slug")

    p_delete = sub.add_parser("delete", help="Delete a roadmap and all its contents")
    p_delete.add_argument("project")
    p_delete.add_argument("slug")

    p_move = sub.add_parser("move", help="Move a roadmap to a different project")
    p_move.add_argument("project", help="Source project slug")
    p_move.add_argument("roadmap", help="Roadmap slug to move")
    p_move.add_argument("--dest", required=True, help="Destination project slug")
    p_move.add_argument("--insert", type=int, help="Insert at position N (1-based) in destination")

    p_hide = sub.add_parser("hide", help="Hide a roadmap from default views")
    p_hide.add_argument("project")
    p_hide.add_argument("slug")

    p_unhide = sub.add_parser("unhide", help="Restore a roadmap to focus")
    p_unhide.add_argument("project")
    p_unhide.add_argument("slug")

    p_list = sub.add_parser("list", help="List roadmaps in a project")
    p_list.add_argument("project", nargs="?", default=None)

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "rename":
        cmd_rename(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "move":
        cmd_move(args)
    elif args.command == "hide":
        cmd_hide(args)
    elif args.command == "unhide":
        cmd_unhide(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
