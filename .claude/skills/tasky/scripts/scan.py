#!/usr/bin/env python3
"""
scan.py — Parse the nimbility project tree and output state as JSON.

Usage:
  python scan.py                        # full project graph
  python scan.py --status DOING         # filter by status
  python scan.py --next                 # first unblocked TODO/PENDING task
  python scan.py --blocked              # tasks/milestones with unmet dependencies
  python scan.py --project <slug>       # scope to a single project
"""

import os
import sys
import json
import re
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT

STATUS_ORDER = ["X", "TODO", "PENDING", "DOING", "PAUSED", "READY", "DONE"]


# ---------------------------------------------------------------------------
# project.json helpers
# ---------------------------------------------------------------------------

def load_project_json(project):
    pjson = os.path.join(NIMBILITY_ROOT, project, "project.json")
    if not os.path.isfile(pjson):
        return {"roadmaps": [], "tracks": {}, "milestones": {}, "tasks": {}, "oob_milestones": {}}
    with open(pjson) as f:
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
    pjson = os.path.join(NIMBILITY_ROOT, project, "project.json")
    with open(pjson, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate_nn_prefixes(project):
    """
    Scan all milestone dirs and task files under this project.
    For any nn-slug name found, strip the prefix, rename, and register in project.json.
    Idempotent — safe to call on every script run.
    """
    data = load_project_json(project)
    project_dir = os.path.join(NIMBILITY_ROOT, project)
    changed = False

    if not os.path.isdir(project_dir):
        return

    # Migrate old-format deps: tracks[track_slug].deps → tracks[roadmap].deps[track_slug]
    all_track_slugs = set()
    for rm in os.listdir(project_dir):
        rm_path = os.path.join(project_dir, rm)
        if not os.path.isdir(rm_path) or rm.startswith('.') or rm == 'project.json':
            continue
        for t in os.listdir(rm_path):
            if os.path.isdir(os.path.join(rm_path, t)) and not t.startswith('.'):
                all_track_slugs.add(t)
    old_deps = {k: v for k, v in data['tracks'].items()
                if k in all_track_slugs and isinstance(v, dict) and isinstance(v.get('deps'), list)}
    if old_deps:
        for roadmap_slug in list(data['roadmaps']) + [
            d for d in os.listdir(project_dir)
            if os.path.isdir(os.path.join(project_dir, d)) and not d.startswith('.') and d != 'project.json'
        ]:
            rm_path = os.path.join(project_dir, roadmap_slug)
            if not os.path.isdir(rm_path):
                continue
            rm_tracks = set(
                d for d in os.listdir(rm_path)
                if os.path.isdir(os.path.join(rm_path, d)) and not d.startswith('.')
            )
            rm_info = data['tracks'].setdefault(roadmap_slug, {})
            deps_dict = rm_info.setdefault('deps', {})
            for track_slug, old_info in old_deps.items():
                if track_slug in rm_tracks:
                    deps_dict[track_slug] = old_info['deps']
        for slug in old_deps:
            del data['tracks'][slug]
        changed = True

    if not data["roadmaps"]:
        for rname in sorted(os.listdir(project_dir)):
            rpath = os.path.join(project_dir, rname)
            if os.path.isdir(rpath) and not rname.startswith(".") and rname != "project.json":
                if rname not in data["roadmaps"]:
                    data["roadmaps"].append(rname)
                    changed = True

    for roadmap in os.listdir(project_dir):
        roadmap_dir = os.path.join(project_dir, roadmap)
        if not os.path.isdir(roadmap_dir) or roadmap.startswith(".") or roadmap == "project.json":
            continue
        for track in os.listdir(roadmap_dir):
            track_dir = os.path.join(roadmap_dir, track)
            if not os.path.isdir(track_dir) or track.startswith("."):
                continue

            rm_info = data["tracks"].setdefault(roadmap, {})
            track_order = rm_info.setdefault("order", [])
            if track not in track_order:
                track_order.append(track)
                changed = True

            m_key = f"{roadmap}/{track}"
            existing_order = data.setdefault("milestones", {}).get(m_key, [])
            oob_slugs = set(data.get("oob_milestones", {}).get(m_key, []))
            new_order = [s for s in existing_order if s not in oob_slugs]
            milestone_entries = sorted(
                [d for d in os.listdir(track_dir) if os.path.isdir(os.path.join(track_dir, d)) and not d.startswith(".")],
                key=lambda d: (re.match(r"^(\d+)-", d) and int(re.match(r"^(\d+)-", d).group(1))) or 999
            )
            for mname in milestone_entries:
                m = re.match(r"^(\d+)-(.+)$", mname)
                if m:
                    slug = m.group(2)
                    if slug in oob_slugs:
                        continue
                    old_path = os.path.join(track_dir, mname)
                    new_path = os.path.join(track_dir, slug)
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                    if slug not in new_order:
                        new_order.append(slug)
                    changed = True
                else:
                    slug = mname
                    if slug in oob_slugs:
                        continue
                    if slug not in new_order:
                        new_order.append(slug)
                        changed = True

            if new_order != existing_order:
                data["milestones"][m_key] = new_order

            for milestone_slug in new_order:
                ms_path = os.path.join(track_dir, milestone_slug)
                if not os.path.isdir(ms_path):
                    continue
                t_key = f"{roadmap}/{track}/{milestone_slug}"
                existing_task_order = data.setdefault("tasks", {}).get(t_key, [])
                new_task_order = list(existing_task_order)
                task_files = sorted(
                    [f for f in os.listdir(ms_path) if f.endswith(".md") and not f.startswith(".")],
                    key=lambda f: (re.match(r"^(\d+)-", f.replace(".md", "")) and int(re.match(r"^(\d+)-", f.replace(".md", "")).group(1))) or 999
                )
                for fname in task_files:
                    base = fname.replace(".md", "")
                    m2 = re.match(r"^(\d+)-(.+)$", base)
                    if m2:
                        slug = m2.group(2)
                        old_path = os.path.join(ms_path, fname)
                        new_path = os.path.join(ms_path, f"{slug}.md")
                        if not os.path.exists(new_path):
                            os.rename(old_path, new_path)
                        if slug not in new_task_order:
                            new_task_order.append(slug)
                        changed = True
                    else:
                        slug = base
                        if slug not in new_task_order:
                            new_task_order.append(slug)
                            changed = True

                if new_task_order != existing_task_order:
                    data["tasks"][t_key] = new_task_order

    # Direction 2: project.json → filesystem — create missing milestone dirs
    for m_key, ms_list in data.get("milestones", {}).items():
        parts = m_key.split("/")
        if len(parts) != 2:
            continue
        roadmap_slug, track_slug = parts
        track_dir = os.path.join(project_dir, roadmap_slug, track_slug)
        for slug in ms_list:
            ms_dir = os.path.join(track_dir, slug)
            if not os.path.isdir(ms_dir):
                os.makedirs(ms_dir, exist_ok=True)

    for m_key, oob_list in data.get("oob_milestones", {}).items():
        parts = m_key.split("/")
        if len(parts) != 2:
            continue
        roadmap_slug, track_slug = parts
        track_dir = os.path.join(project_dir, roadmap_slug, track_slug)
        for slug in oob_list:
            ms_dir = os.path.join(track_dir, slug)
            if not os.path.isdir(ms_dir):
                os.makedirs(ms_dir, exist_ok=True)

    if changed:
        save_project_json(project, data)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_task_file(path):
    """Parse a task.md file and return a dict of its structured fields + metadata."""
    with open(path, "r") as f:
        content = f.read()

    task = {
        "path": path,
        "title": "",
        "status": "X",
        "dependencies": [],
        "references": [],
        "flow": "",
        "criteria": {"total": 0, "done": 0},
    }

    lines = content.splitlines()

    for line in lines:
        if line.startswith("# "):
            task["title"] = line[2:].strip()
            break

    in_header = True
    for line in lines:
        if line.startswith("## "):
            in_header = False
            break
        if not in_header:
            break

        m = re.match(r"^Status:\s*(.+)$", line)
        if m:
            task["status"] = m.group(1).strip()

        m = re.match(r"^Dependencies:\s*\[(.*)\]$", line)
        if m:
            raw = m.group(1).strip()
            task["dependencies"] = [d.strip() for d in raw.split(",") if d.strip()]

        m = re.match(r"^Flow:\s*(.*)$", line)
        if m:
            task["flow"] = m.group(1).strip()

    total = len(re.findall(r"^\s*[-*+]\s+\[[ x]\]", content, re.MULTILINE))
    done = len(re.findall(r"^\s*[-*+]\s+\[x\]", content, re.MULTILINE))
    task["criteria"] = {"total": total, "done": done}

    in_refs = False
    for line in lines:
        if line.strip() == "## References":
            in_refs = True
            continue
        if in_refs:
            if line.startswith("## "):
                break
            m = re.match(r"^\s*-\s+(.+)$", line)
            if m:
                ref = m.group(1).split(" — ")[0].split(" - ")[0].strip()
                if ref:
                    task["references"].append(ref)

    return task


# ---------------------------------------------------------------------------
# Tree walking
# ---------------------------------------------------------------------------

def walk_tree(root):
    """Walk the nimbility root and return a nested project graph."""
    projects = []

    if not os.path.isdir(root):
        return projects

    for project_name in sorted(os.listdir(root)):
        project_path = os.path.join(root, project_name)
        if not os.path.isdir(project_path) or project_name.startswith("."):
            continue

        migrate_nn_prefixes(project_name)
        data = load_project_json(project_name)

        project = {
            "name": project_name,
            "slug": project_name,
            "path": project_path,
            "roadmaps": [],
        }

        # Use project.json roadmap order, include OOB
        roadmap_order = data["roadmaps"]
        oob_roadmap_set = set(data["oob_roadmaps"].get(project_name, []))
        fs_roadmaps = sorted([
            d for d in os.listdir(project_path)
            if os.path.isdir(os.path.join(project_path, d)) and not d.startswith(".") and d != "project.json"
        ])
        ordered_roadmaps = roadmap_order + [r for r in fs_roadmaps if r not in roadmap_order and r not in oob_roadmap_set]
        ordered_roadmaps += sorted(oob_roadmap_set)

        for roadmap_name in ordered_roadmaps:
            roadmap_path = os.path.join(project_path, roadmap_name)
            if not os.path.isdir(roadmap_path):
                continue

            roadmap = {
                "name": roadmap_name,
                "slug": roadmap_name,
                "path": roadmap_path,
                "tracks": [],
            }

            # Use project.json track order, include OOB
            rm_info = data["tracks"].get(roadmap_name, {})
            track_order = rm_info.get("order", [])
            oob_track_set = set(data["oob_tracks"].get(roadmap_name, []))
            fs_tracks = sorted([
                d for d in os.listdir(roadmap_path)
                if os.path.isdir(os.path.join(roadmap_path, d)) and not d.startswith(".")
            ])
            ordered_tracks = track_order + [t for t in fs_tracks if t not in track_order and t not in oob_track_set]
            ordered_tracks += sorted(oob_track_set)

            for track_name in ordered_tracks:
                track_path = os.path.join(roadmap_path, track_name)
                if not os.path.isdir(track_path):
                    continue

                track = {
                    "name": track_name,
                    "slug": track_name,
                    "path": track_path,
                    "milestones": [],
                }

                # Use project.json milestone order, include OOB
                m_key = f"{roadmap_name}/{track_name}"
                oob_ms_set = set(data["oob_milestones"].get(m_key, []))
                ms_order = data["milestones"].get(m_key, [])
                if not ms_order:
                    ms_order = sorted([
                        d for d in os.listdir(track_path)
                        if os.path.isdir(os.path.join(track_path, d)) and not d.startswith(".")
                        and d not in oob_ms_set
                    ])
                all_ms = list(ms_order) + sorted(oob_ms_set)

                for milestone_slug in all_ms:
                    milestone_path = os.path.join(track_path, milestone_slug)
                    if not os.path.isdir(milestone_path):
                        continue
                    milestone = {
                        "name": milestone_slug,
                        "slug": milestone_slug,
                        "path": milestone_path,
                        "tasks": [],
                    }

                    # Use project.json task order, include OOB
                    t_key = f"{roadmap_name}/{track_name}/{milestone_slug}"
                    task_order = data["tasks"].get(t_key, [])
                    oob_task_slugs = data["oob_tasks"].get(t_key, [])
                    if not task_order:
                        task_order = sorted([
                            f.replace(".md", "")
                            for f in os.listdir(milestone_path)
                            if f.endswith(".md") and not f.startswith(".")
                            and f.replace(".md", "") not in oob_task_slugs
                        ])
                    task_order = task_order + [s for s in oob_task_slugs if s not in task_order]

                    for task_slug in task_order:
                        task_path = os.path.join(milestone_path, f"{task_slug}.md")
                        if not os.path.isfile(task_path):
                            continue
                        task = parse_task_file(task_path)
                        task["name"] = task_slug
                        task["slug"] = task_slug
                        milestone["tasks"].append(task)

                    milestone["status"] = rollup_status([t["status"] for t in milestone["tasks"]])
                    track["milestones"].append(milestone)

                track["status"] = rollup_status([m["status"] for m in track["milestones"]])
                roadmap["tracks"].append(track)

            roadmap["status"] = rollup_status([t["status"] for t in roadmap["tracks"]])
            project["roadmaps"].append(roadmap)

        project["status"] = rollup_status([r["status"] for r in project["roadmaps"]])
        projects.append(project)

    return projects


# ---------------------------------------------------------------------------
# Status rollup
# ---------------------------------------------------------------------------

def rollup_status(statuses):
    """Compute rollup status from a list of child statuses."""
    if not statuses:
        return "X"
    non_x = [s for s in statuses if s.upper() != "X"]
    if not non_x:
        return "X"
    upper = [s.upper() for s in non_x]
    if all(s == "DONE" for s in upper):
        return "DONE"
    if any(s == "DOING" for s in upper):
        return "DOING"
    if any(s == "READY" for s in upper):
        return "READY"
    if any(s == "PAUSED" for s in upper):
        return "PAUSED"
    if any(s == "DONE" for s in upper):
        return "DOING"
    if any(s in ("PENDING", "TODO") for s in upper):
        return "PENDING"
    return "X"


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def all_tasks(projects):
    """Flatten the tree into a list of (task, context) tuples."""
    result = []
    for project in projects:
        for roadmap in project["roadmaps"]:
            for track in roadmap["tracks"]:
                for milestone in track["milestones"]:
                    for task in milestone["tasks"]:
                        result.append({
                            "task": task,
                            "project": project["slug"],
                            "roadmap": roadmap["slug"],
                            "track": track["slug"],
                            "milestone": milestone["slug"],
                        })
    return result


def filter_by_status(projects, status):
    """Return all tasks matching a given status."""
    return [t for t in all_tasks(projects) if t["task"]["status"].upper() == status.upper()]


def find_next(projects):
    """Return the first unblocked TODO/PENDING task in sequence order."""
    flat = all_tasks(projects)
    done_slugs = {t["task"]["slug"] for t in flat if t["task"]["status"].upper() == "DONE"}

    for entry in flat:
        task = entry["task"]
        if task["status"].upper() not in ("TODO", "PENDING"):
            continue
        deps_met = all(dep in done_slugs for dep in task["dependencies"])
        if deps_met:
            return entry
    return None


def find_blocked(projects):
    """Return tasks with unmet dependencies."""
    flat = all_tasks(projects)
    done_slugs = {t["task"]["slug"] for t in flat if t["task"]["status"].upper() == "DONE"}

    blocked = []
    for entry in flat:
        task = entry["task"]
        if task["status"].upper() == "DONE":
            continue
        unmet = [dep for dep in task["dependencies"] if dep not in done_slugs]
        if unmet:
            blocked.append({**entry, "unmet_deps": unmet})
    return blocked


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scan nimbility project tree.")
    parser.add_argument("--status", help="Filter tasks by status")
    parser.add_argument("--next", action="store_true", help="Show next unblocked task")
    parser.add_argument("--blocked", action="store_true", help="Show blocked tasks")
    parser.add_argument("--project", help="Scope to a single project slug")
    args = parser.parse_args()

    projects = walk_tree(NIMBILITY_ROOT)

    if args.project:
        projects = [p for p in projects if p["slug"] == args.project]

    if args.status:
        result = filter_by_status(projects, args.status.upper())
        print(json.dumps(result, indent=2))
    elif args.next:
        result = find_next(projects)
        print(json.dumps(result, indent=2))
    elif args.blocked:
        result = find_blocked(projects)
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(projects, indent=2))


if __name__ == "__main__":
    main()
