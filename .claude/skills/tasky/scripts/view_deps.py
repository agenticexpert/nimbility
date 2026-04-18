#!/usr/bin/env python3
"""
view_deps.py — Render a terminal ASCII dependency tree.

Usage:
    python view_deps.py <project> <roadmap>                   — track deps in a roadmap
    python view_deps.py <project> <roadmap> <track> <milestone> — task deps in a milestone
"""

import os
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT

STATUS_CHAR = {
    "done":    "█",
    "doing":   "▓",
    "ready":   "▓",
    "paused":  "▒",
    "pending": "░",
    "todo":    "░",
    "x":       " ",
}


# ---------------------------------------------------------------------------
# project.json
# ---------------------------------------------------------------------------

def load_project_json(project):
    pjson = os.path.join(NIMBILITY_ROOT, project, "project.json")
    if not os.path.isfile(pjson):
        return {"tasks": {}, "oob_tasks": {}, "tracks": {}, "milestones": {}}
    with open(pjson) as f:
        data = json.load(f)
    data.setdefault("roadmaps", [])
    data.setdefault("tasks", {})
    data.setdefault("oob_roadmaps", {})
    data.setdefault("oob_tracks", {})
    data.setdefault("oob_tasks", {})
    data.setdefault("tracks", {})
    data.setdefault("milestones", {})
    data.setdefault("oob_milestones", {})
    data.setdefault("milestone_deps", {})
    return data


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def parse_task_file(path):
    text = Path(path).read_text(encoding="utf-8")
    title = ""
    status = "x"
    deps = []
    for line in text.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        m = re.match(r"^Status:\s*(.+)$", line)
        if m:
            status = m.group(1).strip().lower()
        m = re.match(r"^Dependencies:\s*\[(.*)\]$", line)
        if m:
            raw = m.group(1).strip()
            deps = [d.strip() for d in raw.split(",") if d.strip()]
    return title, status, deps


def load_tasks(milestone_dir, task_order):
    if not task_order:
        task_order = sorted([
            f.replace(".md", "")
            for f in os.listdir(milestone_dir)
            if f.endswith(".md") and not f.startswith(".")
        ])
    tasks = []
    for seq, slug in enumerate(task_order, 1):
        fpath = os.path.join(milestone_dir, f"{slug}.md")
        if not os.path.isfile(fpath):
            continue
        title, status, deps = parse_task_file(fpath)
        tasks.append({"seq": seq, "slug": slug, "status": status, "deps": deps})
    return tasks


# ---------------------------------------------------------------------------
# Track loading
# ---------------------------------------------------------------------------

def rollup(statuses):
    non_x = [s for s in statuses if s != "x"]
    if not non_x:
        return "x"
    if all(s == "done" for s in non_x):
        return "done"
    if any(s == "doing" for s in non_x):
        return "doing"
    if any(s == "ready" for s in non_x):
        return "ready"
    if any(s == "paused" for s in non_x):
        return "paused"
    return "pending"


def track_status(project, roadmap, track_slug, data):
    track_dir = os.path.join(NIMBILITY_ROOT, project, roadmap, track_slug)
    if not os.path.isdir(track_dir):
        return "x"
    m_key = f"{roadmap}/{track_slug}"
    ms_order = data["milestones"].get(m_key, [])
    oob_slugs = set(data.get("oob_milestones", {}).get(m_key, []))
    if not ms_order:
        ms_order = sorted([
            d for d in os.listdir(track_dir)
            if os.path.isdir(os.path.join(track_dir, d)) and not d.startswith(".")
            and d not in oob_slugs
        ])
    all_ms = list(ms_order) + sorted(oob_slugs)
    task_statuses = []
    for mslug in all_ms:
        mpath = os.path.join(track_dir, mslug)
        if not os.path.isdir(mpath):
            continue
        t_key = f"{roadmap}/{track_slug}/{mslug}"
        task_order = data["tasks"].get(t_key, [])
        oob_task_slugs = data["oob_tasks"].get(t_key, [])
        all_slugs = task_order + [s for s in oob_task_slugs if s not in task_order]
        if not all_slugs:
            all_slugs = sorted([
                f.replace(".md", "") for f in os.listdir(mpath)
                if f.endswith(".md") and not f.startswith(".")
            ])
        for slug in all_slugs:
            fpath = os.path.join(mpath, f"{slug}.md")
            if os.path.isfile(fpath):
                with open(fpath) as f:
                    for line in f:
                        m = re.match(r"^Status:\s*(.+)$", line.strip())
                        if m:
                            task_statuses.append(m.group(1).strip().lower())
                            break
    return rollup(task_statuses)


def milestone_status(project, roadmap, track, mslug, data):
    mpath = os.path.join(NIMBILITY_ROOT, project, roadmap, track, mslug)
    if not os.path.isdir(mpath):
        return "x"
    t_key = f"{roadmap}/{track}/{mslug}"
    task_order = data["tasks"].get(t_key, [])
    oob_task_slugs = data["oob_tasks"].get(t_key, [])
    all_slugs = task_order + [s for s in oob_task_slugs if s not in task_order]
    if not all_slugs:
        all_slugs = sorted([
            f.replace(".md", "") for f in os.listdir(mpath)
            if f.endswith(".md") and not f.startswith(".")
        ])
    task_statuses = []
    for slug in all_slugs:
        fpath = os.path.join(mpath, f"{slug}.md")
        if os.path.isfile(fpath):
            with open(fpath) as f:
                for line in f:
                    m = re.match(r"^Status:\s*(.+)$", line.strip())
                    if m:
                        task_statuses.append(m.group(1).strip().lower())
                        break
    return rollup(task_statuses)


def load_milestones(project, roadmap, track, data):
    m_key = f"{roadmap}/{track}"
    ms_order  = data["milestones"].get(m_key, [])
    oob_slugs = set(data.get("oob_milestones", {}).get(m_key, []))
    deps_dict = data.get("milestone_deps", {})

    track_dir = os.path.join(NIMBILITY_ROOT, project, roadmap, track)
    if not os.path.isdir(track_dir):
        return []

    if not ms_order:
        ms_order = sorted([
            d for d in os.listdir(track_dir)
            if os.path.isdir(os.path.join(track_dir, d)) and not d.startswith(".")
            and d not in oob_slugs
        ])
    all_slugs = ms_order + [s for s in sorted(oob_slugs) if s not in ms_order]

    milestones = []
    for seq, slug in enumerate(all_slugs, 1):
        if not os.path.isdir(os.path.join(track_dir, slug)):
            continue
        status = milestone_status(project, roadmap, track, slug, data)
        dep_key = f"{roadmap}/{track}/{slug}"
        milestones.append({
            "seq":    seq,
            "slug":   slug,
            "status": status,
            "deps":   deps_dict.get(dep_key, []),
        })
    return milestones


def load_tracks(project, roadmap, data):
    rm_info = data["tracks"].get(roadmap, {})
    track_order = rm_info.get("order", [])
    deps_dict   = rm_info.get("deps", {})

    roadmap_dir = os.path.join(NIMBILITY_ROOT, project, roadmap)
    if not os.path.isdir(roadmap_dir):
        return []

    fs_tracks = sorted([
        d for d in os.listdir(roadmap_dir)
        if os.path.isdir(os.path.join(roadmap_dir, d)) and not d.startswith(".")
    ])
    all_slugs = track_order + [t for t in fs_tracks if t not in track_order]

    tracks = []
    for seq, slug in enumerate(all_slugs, 1):
        if not os.path.isdir(os.path.join(roadmap_dir, slug)):
            continue
        status = track_status(project, roadmap, slug, data)
        tracks.append({
            "seq":  seq,
            "slug": slug,
            "status": status,
            "deps": deps_dict.get(slug, []),
        })
    return tracks


# ---------------------------------------------------------------------------
# Rendering (shared)
# ---------------------------------------------------------------------------

def render(title, nodes, footer_label):
    if not nodes:
        return f"{title}\n(none)"

    slug_to_node = {n["slug"]: n for n in nodes}
    seq_w = len(str(len(nodes)))

    # Children map: parent → [children] sorted by seq
    children = defaultdict(list)
    for n in nodes:
        for dep in n["deps"]:
            if dep in slug_to_node:
                children[dep].append(n["slug"])
    for slug in children:
        children[slug].sort(key=lambda s: slug_to_node[s]["seq"])

    # Roots: no deps within this set
    roots = [n for n in nodes if not any(d in slug_to_node for d in n["deps"])]
    roots.sort(key=lambda n: n["seq"])

    visited = set()
    lines = []

    def node_label(n):
        seq_str = str(n["seq"]).zfill(seq_w)
        sc = STATUS_CHAR.get(n["status"], "?")
        return f"[{sc}] {seq_str}  {n['slug']}"

    def walk(slug, indent, is_last):
        n = slug_to_node[slug]
        connector = "└►" if is_last else "├►"
        if slug in visited:
            lines.append(f"  {indent}{connector}{node_label(n)}  ↩")
            return
        visited.add(slug)
        lines.append(f"  {indent}{connector}{node_label(n)}")
        kids = children.get(slug, [])
        child_indent = indent + ("   " if is_last else "│  ")
        for i, kid in enumerate(kids):
            walk(kid, child_indent, i == len(kids) - 1)

    out = [f"  {title}", ""]

    for i, root in enumerate(roots):
        visited.add(root["slug"])
        lines.append(f"  {node_label(root)}")
        kids = children.get(root["slug"], [])
        for j, kid in enumerate(kids):
            walk(kid, "", j == len(kids) - 1)
        if i < len(roots) - 1:
            lines.append("")

    out.extend(lines)
    out.append("")
    out.append(f"  {footer_label}   █ done  ▓ doing  ▒ paused  ░ pending")
    out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    argc = len(sys.argv)
    if argc == 3:
        project, roadmap = sys.argv[1], sys.argv[2]
        data   = load_project_json(project)
        tracks = load_tracks(project, roadmap, data)
        done   = sum(1 for t in tracks if t["status"] == "done")
        total  = len(tracks)
        print(render(roadmap, tracks, f"{done}/{total} tracks done"))

    elif argc == 4:
        project, roadmap, track = sys.argv[1:]
        data       = load_project_json(project)
        milestones = load_milestones(project, roadmap, track, data)
        done       = sum(1 for m in milestones if m["status"] == "done")
        total      = len(milestones)
        print(render(track, milestones, f"{done}/{total} milestones done"))

    elif argc == 5:
        project, roadmap, track, milestone = sys.argv[1:]
        data = load_project_json(project)
        milestone_dir = os.path.join(NIMBILITY_ROOT, project, roadmap, track, milestone)
        if not os.path.isdir(milestone_dir):
            print(f"Error: milestone '{milestone}' not found.", file=sys.stderr)
            sys.exit(1)
        t_key    = f"{roadmap}/{track}/{milestone}"
        slugs    = data["tasks"].get(t_key, [])
        oob      = sorted(data["oob_tasks"].get(t_key, []))
        all_slugs = slugs + [s for s in oob if s not in slugs]
        tasks    = load_tasks(milestone_dir, all_slugs)
        done     = sum(1 for t in tasks if t["status"] == "done")
        total    = len(tasks)
        print(render(milestone, tasks, f"{done}/{total} tasks done"))

    else:
        print("Usage:")
        print("  view_deps.py <project> <roadmap>                     — track deps")
        print("  view_deps.py <project> <roadmap> <track>             — milestone deps")
        print("  view_deps.py <project> <roadmap> <track> <milestone> — task deps")
        sys.exit(1)


if __name__ == "__main__":
    main()
