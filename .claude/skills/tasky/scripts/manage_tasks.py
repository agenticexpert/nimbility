#!/usr/bin/env python3
"""
manage_tasks.py — Create, move, and manage tasks within a milestone.

Usage:
  python manage_tasks.py create <project> <roadmap> <track> <milestone> <slug> [--insert <n>] [--deps <slug,...>]
  python manage_tasks.py rename <project> <roadmap> <track> <milestone> <slug> <new-slug>
  python manage_tasks.py delete <project> <roadmap> <track> <milestone> <slug>
  python manage_tasks.py move <project> <roadmap> <track> <milestone> <slug> [--insert <n>] [--dest <roadmap/track/milestone>]
  python manage_tasks.py add-dep <project> <roadmap> <track> <milestone> <slug> <dep-slug>
  python manage_tasks.py remove-dep <project> <roadmap> <track> <milestone> <slug> <dep-slug>
  python manage_tasks.py set-status <project> <roadmap> <track> <milestone> <slug> <status>
  python manage_tasks.py list <project> <roadmap> <track> <milestone>
"""

import os
import sys
import json
import re
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT, validate_slug, validate_slash_path

VALID_STATUSES = {"X", "TODO", "PENDING", "DOING", "PAUSED", "READY", "DONE"}

TASK_TEMPLATE = """# {title}

Status: TODO
Dependencies: [{deps}]
Flow:

## Description


## Goal


## Criteria


## References


## Task

"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def milestone_path(project, roadmap, track, milestone):
    """Plain-slug milestone path — no nn- prefix."""
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

def slug_to_title(slug):
    return slug.replace("-", " ").title()

def read_task_status(task_path):
    with open(task_path) as f:
        for line in f:
            m = re.match(r"^Status:\s*(.+)$", line.strip())
            if m:
                return m.group(1).strip()
    return "X"

def write_task_status(task_path, new_status):
    with open(task_path) as f:
        content = f.read()
    content = re.sub(r"^Status:.*$", f"Status: {new_status}", content, flags=re.MULTILINE)
    with open(task_path, "w") as f:
        f.write(content)


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    validate_slug(args.slug, "task slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    deps = [d.strip() for d in args.deps.split(",")] if args.deps else []
    for dep in deps:
        validate_slug(dep, "task dependency slug")

    data = load_project_json(args.project)
    t_key = f"{args.roadmap}/{args.track}/{args.milestone}"

    if getattr(args, "oob", False):
        order = data["oob_tasks"].setdefault(t_key, [])
        if args.slug not in order:
            order.append(args.slug)
    else:
        order = data["tasks"].setdefault(t_key, [])

        if args.insert:
            insert_at = max(1, min(args.insert, len(order) + 1)) - 1  # 0-based
            order.insert(insert_at, args.slug)
        else:
            order.append(args.slug)

        # Validate deps point backward
        if deps:
            my_pos = order.index(args.slug)
            violations = []
            for dep in deps:
                if dep not in order:
                    violations.append(f"  '{dep}' not found in this milestone")
                elif order.index(dep) >= my_pos:
                    violations.append(f"  '{dep}' is not before '{args.slug}' — dependencies must point backward")
            if violations:
                order.remove(args.slug)
                print("Dependency violations:", file=sys.stderr)
                for v in violations:
                    print(v, file=sys.stderr)
                sys.exit(1)

    task_file = os.path.join(mpath, f"{args.slug}.md")
    assert_not_exists(task_file, f"task '{args.slug}'")

    content = TASK_TEMPLATE.format(
        title=slug_to_title(args.slug),
        deps=", ".join(deps)
    )
    with open(task_file, "w") as f:
        f.write(content)

    save_project_json(args.project, data)
    print(f"Created task: {task_file}")


def cmd_rename(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    validate_slug(args.slug, "task slug")
    validate_slug(args.new_slug, "new task slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    old_file = os.path.join(mpath, f"{args.slug}.md")
    new_file = os.path.join(mpath, f"{args.new_slug}.md")
    if not os.path.isfile(old_file):
        print(f"Error: task '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)
    assert_not_exists(new_file, f"task '{args.new_slug}'")

    # Update title in file
    with open(old_file) as f:
        content = f.read()
    old_title = slug_to_title(args.slug)
    new_title = slug_to_title(args.new_slug)
    content = content.replace(f"# {old_title}", f"# {new_title}", 1)
    with open(old_file, "w") as f:
        f.write(content)

    os.rename(old_file, new_file)

    data = load_project_json(args.project)
    t_key = f"{args.roadmap}/{args.track}/{args.milestone}"
    order = data["tasks"].get(t_key, [])
    if args.slug in order:
        order[order.index(args.slug)] = args.new_slug
    oob_order = data["oob_tasks"].get(t_key, [])
    if args.slug in oob_order:
        oob_order[oob_order.index(args.slug)] = args.new_slug
    save_project_json(args.project, data)

    print(f"Renamed task '{args.slug}' → '{args.new_slug}'")


def cmd_delete(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    validate_slug(args.slug, "task slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    task_file = os.path.join(mpath, f"{args.slug}.md")
    if not os.path.isfile(task_file):
        print(f"Error: task '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)

    os.remove(task_file)

    data = load_project_json(args.project)
    t_key = f"{args.roadmap}/{args.track}/{args.milestone}"
    order = data["tasks"].get(t_key, [])
    if args.slug in order:
        order.remove(args.slug)
    oob_order = data["oob_tasks"].get(t_key, [])
    if args.slug in oob_order:
        oob_order.remove(args.slug)
        if not oob_order:
            data["oob_tasks"].pop(t_key, None)
    save_project_json(args.project, data)

    print(f"Deleted task '{args.slug}'")


def read_task_deps(task_path):
    """Return the list of dep slugs declared in a task file."""
    if not os.path.isfile(task_path):
        return []
    with open(task_path) as f:
        for line in f:
            m = re.match(r"^Dependencies:\s*\[(.*)\]", line.strip())
            if m:
                raw = m.group(1).strip()
                return [d.strip() for d in raw.split(",") if d.strip()] if raw else []
    return []


def cmd_move(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    validate_slug(args.slug, "task slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    data = load_project_json(args.project)
    t_key = f"{args.roadmap}/{args.track}/{args.milestone}"
    order = data["tasks"].get(t_key, [])

    if args.slug not in order:
        print(f"Error: task '{args.slug}' not found in order.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------ cross-parent move
    if args.dest:
        dest_roadmap, dest_track, dest_milestone = validate_slash_path(args.dest, 3, "destination path")

        dest_mpath = milestone_path(args.project, dest_roadmap, dest_track, dest_milestone)
        assert_exists(dest_mpath, f"destination milestone '{args.dest}'")

        dest_t_key = f"{dest_roadmap}/{dest_track}/{dest_milestone}"
        dest_order = data["tasks"].get(dest_t_key, [])

        if args.slug in dest_order:
            print(f"Error: task '{args.slug}' already exists in destination milestone '{args.dest}'.", file=sys.stderr)
            sys.exit(1)

        # Dep check — old siblings only
        task_file = os.path.join(mpath, f"{args.slug}.md")
        my_deps = read_task_deps(task_file)
        old_sibling_slugs = set(order) - {args.slug}

        outbound_conflicts = [d for d in my_deps if d in old_sibling_slugs]

        inbound_conflicts = []
        for sibling_slug in old_sibling_slugs:
            sibling_file = os.path.join(mpath, f"{sibling_slug}.md")
            sibling_deps = read_task_deps(sibling_file)
            if args.slug in sibling_deps:
                inbound_conflicts.append(sibling_slug)

        if outbound_conflicts or inbound_conflicts:
            old_loc = f"{args.roadmap}/{args.track}/{args.milestone}"
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

        # Perform the move — filesystem first
        src_file = os.path.join(mpath, f"{args.slug}.md")
        dst_file = os.path.join(dest_mpath, f"{args.slug}.md")
        shutil.move(src_file, dst_file)

        # Update project.json
        order.remove(args.slug)
        if not order:
            data["tasks"].pop(t_key, None)
        dest_order_list = data["tasks"].setdefault(dest_t_key, [])
        if args.insert:
            insert_at = max(1, min(args.insert, len(dest_order_list) + 1)) - 1
            dest_order_list.insert(insert_at, args.slug)
        else:
            dest_order_list.append(args.slug)

        save_project_json(args.project, data)
        print(f"Moved task '{args.slug}' from '{args.roadmap}/{args.track}/{args.milestone}' to '{args.dest}'.")
        return

    # ------------------------------------------------------------------ same-parent reorder
    if args.insert is None:
        print("Error: --insert is required when --dest is not specified.", file=sys.stderr)
        sys.exit(1)

    order.remove(args.slug)
    insert_at = max(1, min(args.insert, len(order) + 1)) - 1  # 0-based
    order.insert(insert_at, args.slug)

    print("Warning: verify no dependency in this milestone points forward after the move.")
    save_project_json(args.project, data)
    print(f"Moved task '{args.slug}' to position {args.insert}.")


def cmd_add_dep(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    validate_slug(args.slug, "task slug")
    validate_slug(args.dep_slug, "dependency task slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    data = load_project_json(args.project)
    t_key = f"{args.roadmap}/{args.track}/{args.milestone}"
    order = data["tasks"].get(t_key, [])

    if args.slug not in order:
        print(f"Error: task '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)
    if args.dep_slug not in order:
        print(f"Error: dependency task '{args.dep_slug}' not found.", file=sys.stderr)
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

    # Write dependency into task file
    task_path = os.path.join(mpath, f"{args.slug}.md")
    with open(task_path) as f:
        content = f.read()

    def add_to_deps(match):
        existing = match.group(1).strip()
        deps = [d.strip() for d in existing.split(",")] if existing else []
        if args.dep_slug not in deps:
            deps.append(args.dep_slug)
        return f"Dependencies: [{', '.join(deps)}]"

    new_content = re.sub(r"^Dependencies:\s*\[(.*)\]", add_to_deps, content, flags=re.MULTILINE)
    with open(task_path, "w") as f:
        f.write(new_content)

    print(f"Added dependency: '{args.slug}' now depends on '{args.dep_slug}'")


def cmd_remove_dep(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    validate_slug(args.slug, "task slug")
    validate_slug(args.dep_slug, "dependency task slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    task_path = os.path.join(mpath, f"{args.slug}.md")
    if not os.path.isfile(task_path):
        print(f"Error: task '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(task_path) as f:
        content = f.read()

    found = [False]

    def remove_from_deps(match):
        existing = match.group(1).strip()
        deps = [d.strip() for d in existing.split(",") if d.strip()] if existing else []
        if args.dep_slug not in deps:
            print(f"Dependency '{args.dep_slug}' not declared for task '{args.slug}'.")
            return match.group(0)
        found[0] = True
        deps = [d for d in deps if d != args.dep_slug]
        return f"Dependencies: [{', '.join(deps)}]"

    new_content = re.sub(r"^Dependencies:\s*\[(.*)\]", remove_from_deps, content, flags=re.MULTILINE)
    with open(task_path, "w") as f:
        f.write(new_content)

    if found[0]:
        print(f"Removed dependency: '{args.slug}' no longer depends on '{args.dep_slug}'")


def cmd_set_status(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    validate_slug(args.slug, "task slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    status = args.status.upper()
    if status not in VALID_STATUSES:
        print(f"Error: invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}", file=sys.stderr)
        sys.exit(1)

    task_path = os.path.join(mpath, f"{args.slug}.md")
    if not os.path.isfile(task_path):
        print(f"Error: task '{args.slug}' not found.", file=sys.stderr)
        sys.exit(1)

    write_task_status(task_path, status)
    print(f"Set '{args.slug}' status to {status}")


def cmd_list(args):
    validate_slug(args.project, "project slug")
    validate_slug(args.roadmap, "roadmap slug")
    validate_slug(args.track, "track slug")
    validate_slug(args.milestone, "milestone slug")
    mpath = milestone_path(args.project, args.roadmap, args.track, args.milestone)
    assert_exists(mpath, f"milestone '{args.milestone}'")

    data = load_project_json(args.project)
    t_key = f"{args.roadmap}/{args.track}/{args.milestone}"
    order = data["tasks"].get(t_key, [])

    oob_order = data["oob_tasks"].get(t_key, [])

    # Fallback: pick up any on-disk tasks not in order or oob_order
    fs_tasks = sorted([
        f.replace(".md", "")
        for f in os.listdir(mpath)
        if f.endswith(".md") and not f.startswith(".")
    ])
    known = set(order) | set(oob_order)
    ordered = order + [t for t in fs_tasks if t not in known]

    if not ordered and not oob_order:
        print("No tasks found.")
        return

    for i, slug in enumerate(ordered, 1):
        task_path = os.path.join(mpath, f"{slug}.md")
        status = read_task_status(task_path) if os.path.isfile(task_path) else "?"
        print(f"  {i:>2}. {slug}  [{status}]")

    if oob_order:
        print("  ---")
        for slug in sorted(oob_order):
            task_path = os.path.join(mpath, f"{slug}.md")
            status = read_task_status(task_path) if os.path.isfile(task_path) else "?"
            print(f"   ·  {slug}  [{status}]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage nimbility tasks.")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Create a task")
    p_create.add_argument("project")
    p_create.add_argument("roadmap")
    p_create.add_argument("track")
    p_create.add_argument("milestone")
    p_create.add_argument("slug")
    p_create.add_argument("--insert", type=int, help="Insert at position N (1-based), shifting others down")
    p_create.add_argument("--deps", help="Comma-separated dependency slugs")
    p_create.add_argument("--oob", action="store_true", help="Create as an out-of-band task (excluded from sequence)")

    p_rename = sub.add_parser("rename", help="Rename a task (keeps its position)")
    p_rename.add_argument("project")
    p_rename.add_argument("roadmap")
    p_rename.add_argument("track")
    p_rename.add_argument("milestone")
    p_rename.add_argument("slug")
    p_rename.add_argument("new_slug")

    p_delete = sub.add_parser("delete", help="Delete a task")
    p_delete.add_argument("project")
    p_delete.add_argument("roadmap")
    p_delete.add_argument("track")
    p_delete.add_argument("milestone")
    p_delete.add_argument("slug")

    p_move = sub.add_parser("move", help="Move a task to a new position or cross-parent destination")
    p_move.add_argument("project")
    p_move.add_argument("roadmap")
    p_move.add_argument("track")
    p_move.add_argument("milestone")
    p_move.add_argument("slug")
    p_move.add_argument("--insert", type=int, help="Insert at position N (1-based) in destination; required for same-parent reorder")
    p_move.add_argument("--dest", help="Destination parent as roadmap/track/milestone (cross-parent move)")

    p_add_dep = sub.add_parser("add-dep", help="Add a dependency to a task")
    p_add_dep.add_argument("project")
    p_add_dep.add_argument("roadmap")
    p_add_dep.add_argument("track")
    p_add_dep.add_argument("milestone")
    p_add_dep.add_argument("slug")
    p_add_dep.add_argument("dep_slug")

    p_remove_dep = sub.add_parser("remove-dep", help="Remove a dependency from a task")
    p_remove_dep.add_argument("project")
    p_remove_dep.add_argument("roadmap")
    p_remove_dep.add_argument("track")
    p_remove_dep.add_argument("milestone")
    p_remove_dep.add_argument("slug")
    p_remove_dep.add_argument("dep_slug")

    p_set_status = sub.add_parser("set-status", help="Set a task's status")
    p_set_status.add_argument("project")
    p_set_status.add_argument("roadmap")
    p_set_status.add_argument("track")
    p_set_status.add_argument("milestone")
    p_set_status.add_argument("slug")
    p_set_status.add_argument("status")

    p_list = sub.add_parser("list", help="List tasks in a milestone")
    p_list.add_argument("project")
    p_list.add_argument("roadmap")
    p_list.add_argument("track")
    p_list.add_argument("milestone")

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
    elif args.command == "set-status":
        cmd_set_status(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
