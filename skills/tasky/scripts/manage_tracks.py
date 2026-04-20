#!/usr/bin/env python3
"""
manage_tracks.py — Create and manage tracks within a roadmap.

Usage:
  python manage_tracks.py create <project> <roadmap> <slug>
  python manage_tracks.py rename <project> <roadmap> <slug> <new-slug>
  python manage_tracks.py delete <project> <roadmap> <slug>
  python manage_tracks.py move <project> <roadmap> <slug> [--insert <n>] [--dest <roadmap>]
  python manage_tracks.py add-dep <project> <roadmap> <track> <dep-track>
  python manage_tracks.py remove-dep <project> <roadmap> <track> <dep-track>
  python manage_tracks.py list <project> <roadmap>
"""

import os
import sys
import json
import re
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT, validate_slug


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def track_path(project, roadmap, track):
    return os.path.join(NIMBILITY_ROOT, project, roadmap, track)

def roadmap_path(project, roadmap):
    return os.path.join(NIMBILITY_ROOT, project, roadmap)

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


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.slug, "track slug")
    assert_exists(roadmap_path(args.project, args.roadmap), f"roadmap '{args.roadmap}'")
    path = track_path(args.project, args.roadmap, args.slug)
    assert_not_exists(path, f"track '{args.slug}'")

    os.makedirs(path)

    data = load_project_json(args.project)
    if args.oob:
        oob_list = data["oob_tracks"].setdefault(args.roadmap, [])
        if args.slug not in oob_list:
            oob_list.append(args.slug)
    else:
        rm_info = data["tracks"].setdefault(args.roadmap, {})
        order = rm_info.setdefault("order", [])
        if args.slug not in order:
            order.append(args.slug)
    save_project_json(args.project, data)

    print(f"Created track: {path}")


def cmd_rename(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.slug, "track slug")
    validate_slug(args.new_slug, "new track slug")
    old_path = track_path(args.project, args.roadmap, args.slug)
    new_path = track_path(args.project, args.roadmap, args.new_slug)
    if not os.path.isdir(old_path):
        print(f"Error: track '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if os.path.exists(new_path):
        print(f"Error: track '{args.new_slug}' already exists.", file=sys.stderr)
        sys.exit(1)
    os.rename(old_path, new_path)

    data = load_project_json(args.project)
    roadmap = args.roadmap
    rm_info = data["tracks"].setdefault(roadmap, {})

    # Update order array
    order = rm_info.get("order", [])
    if args.slug in order:
        idx = order.index(args.slug)
        order[idx] = args.new_slug

    # Update oob_tracks
    oob_list = data["oob_tracks"].get(roadmap, [])
    if args.slug in oob_list:
        oob_list[oob_list.index(args.slug)] = args.new_slug

    # Update deps dict: rename key and references
    deps_dict = rm_info.get("deps", {})
    if args.slug in deps_dict:
        deps_dict[args.new_slug] = deps_dict.pop(args.slug)
    for t_slug, dep_list in deps_dict.items():
        deps_dict[t_slug] = [args.new_slug if d == args.slug else d for d in dep_list]

    # Update milestones, oob_milestones, tasks, oob_tasks, milestone_deps keys
    old_prefix = f"{roadmap}/{args.slug}/"
    new_prefix = f"{roadmap}/{args.new_slug}/"
    exact_old  = f"{roadmap}/{args.slug}"
    exact_new  = f"{roadmap}/{args.new_slug}"
    for mapping in (data["milestones"], data["oob_milestones"], data["tasks"],
                    data["oob_tasks"], data["milestone_deps"]):
        for key in list(mapping.keys()):
            if key == exact_old:
                mapping[exact_new] = mapping.pop(key)
            elif key.startswith(old_prefix):
                mapping[new_prefix + key[len(old_prefix):]] = mapping.pop(key)

    save_project_json(args.project, data)
    print(f"Renamed track '{args.slug}' → '{args.new_slug}'")


def cmd_delete(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.slug, "track slug")
    path = track_path(args.project, args.roadmap, args.slug)
    if not os.path.isdir(path):
        print(f"Error: track '{args.slug}' does not exist.", file=sys.stderr)
        sys.exit(1)
    shutil.rmtree(path)

    data = load_project_json(args.project)
    roadmap = args.roadmap
    rm_info = data["tracks"].get(roadmap, {})

    # Remove from order
    order = rm_info.get("order", [])
    if args.slug in order:
        order.remove(args.slug)

    # Remove from oob_tracks
    oob_list = data["oob_tracks"].get(args.roadmap, [])
    if args.slug in oob_list:
        oob_list.remove(args.slug)

    # Remove from deps dict
    deps_dict = rm_info.get("deps", {})
    deps_dict.pop(args.slug, None)
    for t_slug in list(deps_dict.keys()):
        deps_dict[t_slug] = [d for d in deps_dict[t_slug] if d != args.slug]

    # Remove milestones, oob_milestones, tasks, oob_tasks, milestone_deps keys for this track
    track_prefix = f"{roadmap}/{args.slug}/"
    exact_key    = f"{roadmap}/{args.slug}"
    for mapping in (data["milestones"], data["oob_milestones"], data["tasks"],
                    data["oob_tasks"], data["milestone_deps"]):
        for key in list(mapping.keys()):
            if key == exact_key or key.startswith(track_prefix):
                del mapping[key]

    save_project_json(args.project, data)
    print(f"Deleted track: {path}")


def cmd_move(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.slug, "track slug")
    src_rmap_path = roadmap_path(args.project, args.roadmap)
    assert_exists(src_rmap_path, f"roadmap '{args.roadmap}'")

    src_track_path = track_path(args.project, args.roadmap, args.slug)
    if not os.path.isdir(src_track_path):
        print(f"Error: track '{args.slug}' does not exist in roadmap '{args.roadmap}'.", file=sys.stderr)
        sys.exit(1)

    data = load_project_json(args.project)
    src_rm_info = data["tracks"].get(args.roadmap, {})
    src_order = src_rm_info.get("order", [])

    if args.slug not in src_order:
        print(f"Error: track '{args.slug}' not found in order for roadmap '{args.roadmap}'.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------ cross-parent move
    if args.dest:
        validate_slug(args.dest, "destination roadmap slug")
        dest_roadmap = args.dest
        dest_rmap_path = roadmap_path(args.project, dest_roadmap)
        assert_exists(dest_rmap_path, f"destination roadmap '{dest_roadmap}'")

        dest_rm_info = data["tracks"].get(dest_roadmap, {})
        dest_order = dest_rm_info.get("order", [])

        if args.slug in dest_order or os.path.isdir(track_path(args.project, dest_roadmap, args.slug)):
            print(f"Error: track '{args.slug}' already exists in destination roadmap '{dest_roadmap}'.", file=sys.stderr)
            sys.exit(1)

        # Dep check
        src_deps_dict = src_rm_info.get("deps", {})
        src_siblings = set(src_order) - {args.slug}

        outbound_conflicts = [d for d in src_deps_dict.get(args.slug, []) if d in src_siblings]

        inbound_conflicts = []
        for sib_slug, sib_dep_list in src_deps_dict.items():
            if sib_slug == args.slug:
                continue
            if sib_slug in src_siblings and args.slug in sib_dep_list:
                inbound_conflicts.append(sib_slug)

        if outbound_conflicts or inbound_conflicts:
            print(f"Error: cannot move '{args.slug}' — dependency conflicts must be resolved first:", file=sys.stderr)
            if outbound_conflicts:
                print("  outbound (this item depends on):", file=sys.stderr)
                for dep in outbound_conflicts:
                    print(f"    - {dep}  [in {args.roadmap}]", file=sys.stderr)
            if inbound_conflicts:
                print("  inbound (other items depend on this):", file=sys.stderr)
                for dep in inbound_conflicts:
                    print(f"    - {dep}  [in {args.roadmap}]", file=sys.stderr)
            print("Remove these dependencies before moving.", file=sys.stderr)
            sys.exit(1)

        # Move filesystem directory
        dst_track_path = track_path(args.project, dest_roadmap, args.slug)
        shutil.move(src_track_path, dst_track_path)

        # Remove from source order
        src_order.remove(args.slug)

        # Move deps entry from source roadmap to dest roadmap
        if args.slug in src_deps_dict:
            dep_val = src_deps_dict.pop(args.slug)
            dest_rm_info_mut = data["tracks"].setdefault(dest_roadmap, {})
            dest_rm_info_mut.setdefault("deps", {})[args.slug] = dep_val

        # Add to dest order
        dest_rm_info_mut = data["tracks"].setdefault(dest_roadmap, {})
        dest_order_list = dest_rm_info_mut.setdefault("order", [])
        if args.insert:
            insert_at = max(1, min(args.insert, len(dest_order_list) + 1)) - 1
            dest_order_list.insert(insert_at, args.slug)
        else:
            dest_order_list.append(args.slug)

        # Migrate milestones keys: old-roadmap/slug/... → dest-roadmap/slug/...
        old_prefix = f"{args.roadmap}/{args.slug}/"
        new_prefix = f"{dest_roadmap}/{args.slug}/"
        for key in list(data["milestones"].keys()):
            if key.startswith(old_prefix):
                data["milestones"][new_prefix + key[len(old_prefix):]] = data["milestones"].pop(key)
            elif key == f"{args.roadmap}/{args.slug}":
                data["milestones"][f"{dest_roadmap}/{args.slug}"] = data["milestones"].pop(key)

        # Migrate tasks keys similarly
        for key in list(data["tasks"].keys()):
            if key.startswith(old_prefix):
                data["tasks"][new_prefix + key[len(old_prefix):]] = data["tasks"].pop(key)

        # Migrate milestone_deps, oob_milestones, oob_tasks keys
        exact_old = f"{args.roadmap}/{args.slug}"
        exact_new = f"{dest_roadmap}/{args.slug}"
        for mapping in (data["milestone_deps"], data["oob_milestones"], data["oob_tasks"]):
            for key in list(mapping.keys()):
                if key == exact_old:
                    mapping[exact_new] = mapping.pop(key)
                elif key.startswith(old_prefix):
                    mapping[new_prefix + key[len(old_prefix):]] = mapping.pop(key)

        # Migrate oob_tracks entry if OOB
        src_oob = data["oob_tracks"].get(args.roadmap, [])
        if args.slug in src_oob:
            src_oob.remove(args.slug)
            data["oob_tracks"].setdefault(dest_roadmap, []).append(args.slug)

        save_project_json(args.project, data)
        print(f"Moved track '{args.slug}' from roadmap '{args.roadmap}' to roadmap '{dest_roadmap}'.")
        return

    # ------------------------------------------------------------------ same-parent reorder
    if args.insert is None:
        print("Error: --insert is required when --dest is not specified.", file=sys.stderr)
        sys.exit(1)

    src_order.remove(args.slug)
    insert_at = max(1, min(args.insert, len(src_order) + 1)) - 1
    src_order.insert(insert_at, args.slug)

    print("Warning: verify no dependency in this roadmap points forward after the move.")
    save_project_json(args.project, data)
    print(f"Moved track '{args.slug}' to position {args.insert} in roadmap '{args.roadmap}'.")


def cmd_add_dep(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.dep_track, "dependency track slug")
    assert_exists(
        track_path(args.project, args.roadmap, args.track),
        f"track '{args.track}'"
    )
    assert_exists(
        track_path(args.project, args.roadmap, args.dep_track),
        f"dep track '{args.dep_track}'"
    )

    data = load_project_json(args.project)
    rm_info = data["tracks"].setdefault(args.roadmap, {})
    deps_dict = rm_info.setdefault("deps", {})
    deps = deps_dict.setdefault(args.track, [])

    if args.dep_track in deps:
        print(f"Dependency '{args.dep_track}' already declared for track '{args.track}'.")
        return

    deps.append(args.dep_track)
    save_project_json(args.project, data)
    print(f"Added dependency: {args.track} depends on {args.dep_track}")


def cmd_remove_dep(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.dep_track, "dependency track slug")
    assert_exists(
        track_path(args.project, args.roadmap, args.track),
        f"track '{args.track}'"
    )
    data = load_project_json(args.project)
    rm_info = data["tracks"].get(args.roadmap, {})
    deps_dict = rm_info.get("deps", {})
    deps = deps_dict.get(args.track, [])

    if args.dep_track not in deps:
        print(f"Dependency '{args.dep_track}' not declared for track '{args.track}'.")
        return

    deps_dict[args.track] = [d for d in deps if d != args.dep_track]
    save_project_json(args.project, data)
    print(f"Removed dependency: {args.track} no longer depends on {args.dep_track}")


def focus_hide_add(data, roadmap, slug):
    hide = data.setdefault("focus", {}).setdefault("hide", {})
    d = hide.setdefault("tracks", {})
    lst = d.setdefault(roadmap, [])
    if slug not in lst:
        lst.append(slug)

def focus_hide_remove(data, roadmap, slug):
    hide = data.get("focus", {}).get("hide", {})
    if not hide:
        return
    d = hide.get("tracks", {})
    lst = d.get(roadmap, [])
    if slug in lst:
        lst.remove(slug)
    if not lst:
        d.pop(roadmap, None)
    if not d:
        hide.pop("tracks", None)
    if not hide:
        data.get("focus", {}).pop("hide", None)
    if not data.get("focus", {}):
        data.pop("focus", None)


def cmd_hide(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.slug, "track slug")
    path = track_path(args.project, args.roadmap, args.slug)
    assert_exists(path, f"track '{args.slug}'")

    data = load_project_json(args.project)
    oob_list = data.get("oob_tracks", {}).get(args.roadmap, [])
    if args.slug in oob_list:
        print(f"Error: OOB tracks cannot be hidden.", file=sys.stderr)
        sys.exit(1)

    focus_hide_add(data, args.roadmap, args.slug)
    save_project_json(args.project, data)
    print(f"Hidden track '{args.slug}' — excluded from default views. Use --all to reveal.")


def cmd_unhide(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.slug, "track slug")
    assert_exists(roadmap_path(args.project, args.roadmap), f"roadmap '{args.roadmap}'")
    data = load_project_json(args.project)
    focus_hide_remove(data, args.roadmap, args.slug)
    save_project_json(args.project, data)
    print(f"Track '{args.slug}' restored to focus.")


def cmd_list(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    path = roadmap_path(args.project, args.roadmap)
    assert_exists(path, f"roadmap '{args.roadmap}'")

    data = load_project_json(args.project)
    rm_info = data["tracks"].get(args.roadmap, {})
    order = rm_info.get("order", [])
    deps_dict = rm_info.get("deps", {})

    # Fall back to filesystem listing for anything not in order
    fs_tracks = sorted([
        d for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")
    ])
    ordered = order + [t for t in fs_tracks if t not in order]

    if not ordered:
        print("No tracks found.")
        return

    for track in ordered:
        deps = deps_dict.get(track, [])
        dep_str = f"  (depends on: {', '.join(deps)})" if deps else ""
        print(f"  {track}{dep_str}")

    oob_list = data["oob_tracks"].get(args.roadmap, [])
    if oob_list:
        print("  ---")
        for track in sorted(oob_list):
            print(f"  · {track}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage nimbility tracks.")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Create a track under a roadmap")
    p_create.add_argument("project")
    p_create.add_argument("roadmap")
    p_create.add_argument("slug")
    p_create.add_argument("--oob", action="store_true", help="Mark as out-of-band (not in sequence)")

    p_rename = sub.add_parser("rename", help="Rename a track")
    p_rename.add_argument("project")
    p_rename.add_argument("roadmap")
    p_rename.add_argument("slug")
    p_rename.add_argument("new_slug")

    p_delete = sub.add_parser("delete", help="Delete a track and all its contents")
    p_delete.add_argument("project")
    p_delete.add_argument("roadmap")
    p_delete.add_argument("slug")

    p_move = sub.add_parser("move", help="Move a track to a new position or cross-parent roadmap")
    p_move.add_argument("project")
    p_move.add_argument("roadmap")
    p_move.add_argument("slug")
    p_move.add_argument("--insert", type=int, help="New position (1-based); required for same-parent reorder")
    p_move.add_argument("--dest", help="Destination roadmap slug (cross-parent move)")

    p_add_dep = sub.add_parser("add-dep", help="Declare a track dependency (writes to project.json)")
    p_add_dep.add_argument("project")
    p_add_dep.add_argument("roadmap")
    p_add_dep.add_argument("track")
    p_add_dep.add_argument("dep_track")

    p_remove_dep = sub.add_parser("remove-dep", help="Remove a track dependency")
    p_remove_dep.add_argument("project")
    p_remove_dep.add_argument("roadmap")
    p_remove_dep.add_argument("track")
    p_remove_dep.add_argument("dep_track")

    p_list = sub.add_parser("list", help="List tracks in a roadmap")
    p_list.add_argument("project")
    p_list.add_argument("roadmap")

    p_hide = sub.add_parser("hide", help="Hide a track from default views")
    p_hide.add_argument("project")
    p_hide.add_argument("roadmap")
    p_hide.add_argument("slug")

    p_unhide = sub.add_parser("unhide", help="Restore a track to focus")
    p_unhide.add_argument("project")
    p_unhide.add_argument("roadmap")
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
    elif args.command == "hide":
        cmd_hide(args)
    elif args.command == "unhide":
        cmd_unhide(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
