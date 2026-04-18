#!/usr/bin/env python3
"""
manage_milestones.py — Create, move, and manage milestones within a track.

Usage:
  python manage_milestones.py create <project> <roadmap> <track> <slug> [--insert <n>] [--deps <slug,...>]
  python manage_milestones.py rename <project> <roadmap> <track> <slug> <new-slug>
  python manage_milestones.py delete <project> <roadmap> <track> <slug>
  python manage_milestones.py move <project> <roadmap> <track> <slug> [--insert <n>] [--dest <roadmap/track>]
  python manage_milestones.py add-dep <project> <roadmap> <track> <slug> <dep-slug>
  python manage_milestones.py remove-dep <project> <roadmap> <track> <slug> <dep-slug>
  python manage_milestones.py list <project> <roadmap> <track>
  python manage_milestones.py mark-oob <project> <roadmap> <track> <slug>
"""

import os
import sys
import json
import re
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT, validate_slug, validate_slash_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def track_path(project, roadmap, track):
    return os.path.join(NIMBILITY_ROOT, project, roadmap, track)

def milestone_path(project, roadmap, track, milestone):
    return os.path.join(NIMBILITY_ROOT, project, roadmap, track, milestone)

def project_json_path(project):
    return os.path.join(NIMBILITY_ROOT, project, "project.json")

def assert_exists(path, label):
    if not os.path.isdir(path):
        print(f"Error: {label} does not exist at {path}", file=sys.stderr)
        sys.exit(1)

def assert_not_exists(path, label):
    if os.path.exists(path):
        print(f"Error: {label} already exists at {path}", file=sys.stderr)
        sys.exit(1)

def load_project_json(project):
    path = project_json_path(project)
    if not os.path.exists(path):
        return {"roadmaps": [], "tracks": {}, "milestones": {}, "tasks": {}}
    with open(path) as f:
        data = json.load(f)
    data.setdefault("roadmaps", [])
    data.setdefault("tracks", {})
    data.setdefault("milestones", {})
    data.setdefault("oob_roadmaps", {})
    data.setdefault("oob_tracks", {})
    data.setdefault("oob_milestones", {})
    data.setdefault("oob_tasks", {})
    data.setdefault("milestone_slots", {})
    data.setdefault("milestone_deps", {})
    data.setdefault("tasks", {})
    return data

def save_project_json(project, data):
    with open(project_json_path(project), "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    mpath = os.path.join(tpath, args.slug)
    assert_not_exists(mpath, f"milestone '{args.slug}'")

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"
    os.makedirs(mpath)

    if getattr(args, "oob", False):
        oob_list = data["oob_milestones"].setdefault(m_key, [])
        if args.slug not in oob_list:
            oob_list.append(args.slug)
        save_project_json(args.project, data)
        print(f"Created OOB milestone: {mpath}")
        return

    deps = [d.strip() for d in args.deps.split(",")] if args.deps else []
    for dep in deps:
        validate_slug(dep, "milestone dependency slug")
    order = data["milestones"].setdefault(m_key, [])

    if args.insert:
        insert_at = max(1, min(args.insert, len(order) + 1)) - 1  # convert to 0-based
        order.insert(insert_at, args.slug)
    else:
        order.append(args.slug)

    # Validate deps point backward
    if deps:
        my_pos = order.index(args.slug)
        violations = []
        for dep in deps:
            if dep not in order:
                violations.append(f"  '{dep}' not found in this track")
            elif order.index(dep) >= my_pos:
                violations.append(f"  '{dep}' is not before '{args.slug}' — dependencies must point backward")
        if violations:
            order.remove(args.slug)
            print("Dependency violations:", file=sys.stderr)
            for v in violations:
                print(v, file=sys.stderr)
            sys.exit(1)

    # Store milestone deps
    if deps:
        data["milestone_deps"][f"{args.roadmap}/{args.track}/{args.slug}"] = deps

    save_project_json(args.project, data)
    print(f"Created milestone: {mpath}")
    if deps:
        print(f"  Dependencies: {deps}")


def cmd_mark_oob(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    mpath = os.path.join(tpath, args.slug)
    if not os.path.isdir(mpath):
        print(f"Error: milestone '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"

    # Remove from sequenced order if present
    order = data["milestones"].get(m_key, [])
    if args.slug in order:
        order.remove(args.slug)

    # Add to oob list
    oob_list = data["oob_milestones"].setdefault(m_key, [])
    if args.slug not in oob_list:
        oob_list.append(args.slug)

    save_project_json(args.project, data)
    print(f"Marked '{args.slug}' as out of bounds")


def cmd_rename(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    validate_slug(args.new_slug, "new milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    old_mpath = os.path.join(tpath, args.slug)
    new_mpath = os.path.join(tpath, args.new_slug)
    if not os.path.isdir(old_mpath):
        print(f"Error: milestone '{args.slug}' not found at {old_mpath}.", file=sys.stderr)
        sys.exit(1)
    assert_not_exists(new_mpath, f"milestone '{args.new_slug}'")

    os.rename(old_mpath, new_mpath)

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"
    order = data["milestones"].get(m_key, [])
    if args.slug in order:
        idx = order.index(args.slug)
        order[idx] = args.new_slug

    # Update tasks keys
    old_t_key = f"{args.roadmap}/{args.track}/{args.slug}"
    new_t_key = f"{args.roadmap}/{args.track}/{args.new_slug}"
    if old_t_key in data["tasks"]:
        data["tasks"][new_t_key] = data["tasks"].pop(old_t_key)

    # Update oob_milestones list entry if OOB
    m_key = f"{args.roadmap}/{args.track}"
    oob_list = data["oob_milestones"].get(m_key, [])
    if args.slug in oob_list:
        oob_list[oob_list.index(args.slug)] = args.new_slug

    # Update oob_tasks keys
    old_t_key = f"{args.roadmap}/{args.track}/{args.slug}"
    new_t_key = f"{args.roadmap}/{args.track}/{args.new_slug}"
    if old_t_key in data["oob_tasks"]:
        data["oob_tasks"][new_t_key] = data["oob_tasks"].pop(old_t_key)

    # Update milestone_deps: rename key and references
    if old_t_key in data["milestone_deps"]:
        data["milestone_deps"][new_t_key] = data["milestone_deps"].pop(old_t_key)
    prefix = f"{args.roadmap}/{args.track}/"
    for key in list(data["milestone_deps"].keys()):
        if key.startswith(prefix):
            data["milestone_deps"][key] = [
                args.new_slug if d == args.slug else d
                for d in data["milestone_deps"][key]
            ]

    save_project_json(args.project, data)
    print(f"Renamed milestone '{args.slug}' → '{args.new_slug}'")


def cmd_delete(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    mpath = os.path.join(tpath, args.slug)
    if not os.path.isdir(mpath):
        print(f"Error: milestone '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)

    shutil.rmtree(mpath)

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"
    order = data["milestones"].get(m_key, [])
    if args.slug in order:
        order.remove(args.slug)

    # Remove from oob_milestones if present
    m_key = f"{args.roadmap}/{args.track}"
    oob_list = data["oob_milestones"].get(m_key, [])
    if args.slug in oob_list:
        oob_list.remove(args.slug)

    # Remove tasks and oob_tasks entries
    t_key = f"{args.roadmap}/{args.track}/{args.slug}"
    data["tasks"].pop(t_key, None)
    data["oob_tasks"].pop(t_key, None)

    # Remove milestone_deps entry and references
    data["milestone_deps"].pop(t_key, None)
    prefix = f"{args.roadmap}/{args.track}/"
    for key in list(data["milestone_deps"].keys()):
        if key.startswith(prefix):
            data["milestone_deps"][key] = [d for d in data["milestone_deps"][key] if d != args.slug]

    save_project_json(args.project, data)
    print(f"Deleted milestone '{args.slug}'")


def cmd_move(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"
    order = data["milestones"].get(m_key, [])

    if args.slug not in order:
        print(f"Error: milestone '{args.slug}' not found in order.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------ cross-parent move
    if args.dest:
        dest_roadmap, dest_track = validate_slash_path(args.dest, 2, "destination path")

        dest_tpath = track_path(args.project, dest_roadmap, dest_track)
        assert_exists(dest_tpath, f"destination track '{args.dest}'")

        dest_m_key = f"{dest_roadmap}/{dest_track}"
        dest_order = data["milestones"].get(dest_m_key, [])

        if args.slug in dest_order:
            print(f"Error: milestone '{args.slug}' already exists in destination track '{args.dest}'.", file=sys.stderr)
            sys.exit(1)

        # Dep check
        old_dep_key = f"{args.roadmap}/{args.track}/{args.slug}"
        my_deps = data["milestone_deps"].get(old_dep_key, [])
        old_siblings = set(order) - {args.slug}

        outbound_conflicts = [d for d in my_deps if d in old_siblings]

        inbound_conflicts = []
        sib_prefix = f"{args.roadmap}/{args.track}/"
        for dep_key_sib, sib_deps in data["milestone_deps"].items():
            if not dep_key_sib.startswith(sib_prefix):
                continue
            sib_slug = dep_key_sib[len(sib_prefix):]
            if sib_slug == args.slug:
                continue
            if sib_slug in old_siblings and args.slug in sib_deps:
                inbound_conflicts.append(sib_slug)

        if outbound_conflicts or inbound_conflicts:
            old_loc = f"{args.roadmap}/{args.track}"
            print(f"Error: cannot move '{args.slug}' — dependency conflicts must be resolved first:", file=sys.stderr)
            if outbound_conflicts:
                print("  outbound (this item depends on):", file=sys.stderr)
                for dep in outbound_conflicts:
                    print(f"    - {dep}  [in {old_loc}]", file=sys.stderr)
            if inbound_conflicts:
                print("  inbound (other items depend on this):", file=sys.stderr)
                for dep in inbound_conflicts:
                    print(f"    - {dep}  [in {old_loc}]", file=sys.stderr)
            print("Remove these dependencies before moving.", file=sys.stderr)
            sys.exit(1)

        # Move the directory
        src_dir = milestone_path(args.project, args.roadmap, args.track, args.slug)
        dst_dir = milestone_path(args.project, dest_roadmap, dest_track, args.slug)
        shutil.move(src_dir, dst_dir)

        # Update milestones order lists
        order.remove(args.slug)
        dest_order_list = data["milestones"].setdefault(dest_m_key, [])
        if args.insert:
            insert_at = max(1, min(args.insert, len(dest_order_list) + 1)) - 1
            dest_order_list.insert(insert_at, args.slug)
        else:
            dest_order_list.append(args.slug)

        # Move tasks key
        old_t_key = f"{args.roadmap}/{args.track}/{args.slug}"
        new_t_key = f"{dest_roadmap}/{dest_track}/{args.slug}"
        if old_t_key in data["tasks"]:
            data["tasks"][new_t_key] = data["tasks"].pop(old_t_key)

        # Move oob_tasks key
        if old_t_key in data["oob_tasks"]:
            data["oob_tasks"][new_t_key] = data["oob_tasks"].pop(old_t_key)

        # Move milestone_deps entry if present
        new_dep_key = f"{dest_roadmap}/{dest_track}/{args.slug}"
        if old_dep_key in data["milestone_deps"]:
            data["milestone_deps"][new_dep_key] = data["milestone_deps"].pop(old_dep_key)

        # Move oob_milestones entry if OOB
        old_m_key = f"{args.roadmap}/{args.track}"
        if args.slug in data["oob_milestones"].get(old_m_key, []):
            data["oob_milestones"][old_m_key].remove(args.slug)
            data["oob_milestones"].setdefault(dest_m_key, []).append(args.slug)

        save_project_json(args.project, data)
        print(f"Moved milestone '{args.slug}' from '{args.roadmap}/{args.track}' to '{args.dest}'.")
        return

    # ------------------------------------------------------------------ same-parent reorder
    if args.insert is None:
        print("Error: --insert is required when --dest is not specified.", file=sys.stderr)
        sys.exit(1)

    order.remove(args.slug)
    insert_at = max(1, min(args.insert, len(order) + 1)) - 1  # convert to 0-based
    order.insert(insert_at, args.slug)

    print("Warning: verify no dependency in this track points forward after the move.")
    save_project_json(args.project, data)
    print(f"Moved milestone '{args.slug}' to position {args.insert}.")


def cmd_add_dep(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    validate_slug(args.dep_slug, "dependency milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"
    order = data["milestones"].get(m_key, [])

    if args.slug not in order:
        print(f"Error: milestone '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)
    if args.dep_slug not in order:
        print(f"Error: dependency milestone '{args.dep_slug}' not found.", file=sys.stderr)
        sys.exit(1)

    my_pos = order.index(args.slug)
    dep_pos = order.index(args.dep_slug)
    if dep_pos >= my_pos:
        print(
            f"Error: '{args.dep_slug}' (position {dep_pos + 1}) is not before "
            f"'{args.slug}' (position {my_pos + 1}). Dependencies must point backward.",
            file=sys.stderr
        )
        sys.exit(1)

    dep_key = f"{args.roadmap}/{args.track}/{args.slug}"
    dep_list = data["milestone_deps"].setdefault(dep_key, [])
    if args.dep_slug not in dep_list:
        dep_list.append(args.dep_slug)
        save_project_json(args.project, data)

    print(f"Dependency validated: {args.slug} depends on {args.dep_slug}")


def cmd_remove_dep(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    validate_slug(args.dep_slug, "dependency milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    data = load_project_json(args.project)
    dep_key = f"{args.roadmap}/{args.track}/{args.slug}"
    dep_list = data["milestone_deps"].get(dep_key, [])

    if args.dep_slug not in dep_list:
        print(f"Dependency '{args.dep_slug}' not declared for milestone '{args.slug}'.")
        return

    data["milestone_deps"][dep_key] = [d for d in dep_list if d != args.dep_slug]
    save_project_json(args.project, data)
    print(f"Dependency reference removed: {args.slug} no longer depends on {args.dep_slug}")


def focus_hide_add(data, roadmap, track, slug):
    hide = data.setdefault("focus", {}).setdefault("hide", {})
    d = hide.setdefault("milestones", {})
    key = f"{roadmap}/{track}"
    lst = d.setdefault(key, [])
    if slug not in lst:
        lst.append(slug)

def focus_hide_remove(data, roadmap, track, slug):
    hide = data.get("focus", {}).get("hide", {})
    if not hide:
        return
    d = hide.get("milestones", {})
    key = f"{roadmap}/{track}"
    lst = d.get(key, [])
    if slug in lst:
        lst.remove(slug)
    if not lst:
        d.pop(key, None)
    if not d:
        hide.pop("milestones", None)
    if not hide:
        data.get("focus", {}).pop("hide", None)
    if not data.get("focus", {}):
        data.pop("focus", None)


def cmd_hide(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    mpath = os.path.join(tpath, args.slug)
    if not os.path.isdir(mpath):
        print(f"Error: milestone '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"
    oob_list = data.get("oob_milestones", {}).get(m_key, [])
    if args.slug in oob_list:
        print(f"Error: OOB milestones cannot be hidden.", file=sys.stderr)
        sys.exit(1)

    focus_hide_add(data, args.roadmap, args.track, args.slug)
    save_project_json(args.project, data)
    print(f"Hidden milestone '{args.slug}' — excluded from default views. Use --all to reveal.")


def cmd_unhide(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.slug, "milestone slug")
    assert_exists(track_path(args.project, args.roadmap, args.track), f"track '{args.track}'")
    data = load_project_json(args.project)
    focus_hide_remove(data, args.roadmap, args.track, args.slug)
    save_project_json(args.project, data)
    print(f"Milestone '{args.slug}' restored to focus.")


def cmd_list(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    tpath = track_path(args.project, args.roadmap, args.track)
    assert_exists(tpath, f"track '{args.track}'")

    data = load_project_json(args.project)
    m_key = f"{args.roadmap}/{args.track}"
    order = data["milestones"].get(m_key, [])
    oob_slugs = set(data.get("oob_milestones", {}).get(m_key, []))

    # Fallback: pick up any on-disk milestones not in order (excluding OOB)
    fs_milestones = sorted([
        d for d in os.listdir(tpath)
        if os.path.isdir(os.path.join(tpath, d)) and not d.startswith(".")
        and d not in oob_slugs
    ])
    ordered = order + [m for m in fs_milestones if m not in order]

    if not ordered:
        print("No milestones found.")
        return

    for i, slug in enumerate(ordered, 1):
        print(f"  {i:>2}. {slug}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage nimbility milestones.")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Create a milestone")
    p_create.add_argument("project")
    p_create.add_argument("roadmap")
    p_create.add_argument("track")
    p_create.add_argument("slug")
    p_create.add_argument("--insert", type=int, help="Insert at position N (1-based), shifting others down")
    p_create.add_argument("--deps", help="Comma-separated dependency slugs")
    p_create.add_argument("--oob", action="store_true", help="Mark as out-of-bounds (no sequence, shown below divider)")

    p_move = sub.add_parser("move", help="Move a milestone to a new position or cross-parent destination")
    p_move.add_argument("project")
    p_move.add_argument("roadmap")
    p_move.add_argument("track")
    p_move.add_argument("slug")
    p_move.add_argument("--insert", type=int, help="New position (1-based); required for same-parent reorder")
    p_move.add_argument("--dest", help="Destination parent as roadmap/track (cross-parent move)")

    p_rename = sub.add_parser("rename", help="Rename a milestone (keeps its position)")
    p_rename.add_argument("project")
    p_rename.add_argument("roadmap")
    p_rename.add_argument("track")
    p_rename.add_argument("slug")
    p_rename.add_argument("new_slug")

    p_delete = sub.add_parser("delete", help="Delete a milestone and all its tasks")
    p_delete.add_argument("project")
    p_delete.add_argument("roadmap")
    p_delete.add_argument("track")
    p_delete.add_argument("slug")

    p_add_dep = sub.add_parser("add-dep", help="Validate and store a milestone dependency")
    p_add_dep.add_argument("project")
    p_add_dep.add_argument("roadmap")
    p_add_dep.add_argument("track")
    p_add_dep.add_argument("slug")
    p_add_dep.add_argument("dep_slug")

    p_remove_dep = sub.add_parser("remove-dep", help="Remove a milestone dependency reference")
    p_remove_dep.add_argument("project")
    p_remove_dep.add_argument("roadmap")
    p_remove_dep.add_argument("track")
    p_remove_dep.add_argument("slug")
    p_remove_dep.add_argument("dep_slug")

    p_list = sub.add_parser("list", help="List milestones in a track")
    p_list.add_argument("project")
    p_list.add_argument("roadmap")
    p_list.add_argument("track")

    p_mark_oob = sub.add_parser("mark-oob", help="Move a milestone out of sequence (out of bounds)")
    p_mark_oob.add_argument("project")
    p_mark_oob.add_argument("roadmap")
    p_mark_oob.add_argument("track")
    p_mark_oob.add_argument("slug")

    p_hide = sub.add_parser("hide", help="Hide a milestone from default views")
    p_hide.add_argument("project")
    p_hide.add_argument("roadmap")
    p_hide.add_argument("track")
    p_hide.add_argument("slug")

    p_unhide = sub.add_parser("unhide", help="Restore a milestone to focus")
    p_unhide.add_argument("project")
    p_unhide.add_argument("roadmap")
    p_unhide.add_argument("track")
    p_unhide.add_argument("slug")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "rename":
        cmd_rename(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "move":
        cmd_move(args)
    elif args.command == "add-dep":
        cmd_add_dep(args)
    elif args.command == "remove-dep":
        cmd_remove_dep(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "mark-oob":
        cmd_mark_oob(args)
    elif args.command == "hide":
        cmd_hide(args)
    elif args.command == "unhide":
        cmd_unhide(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
