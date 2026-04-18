#!/usr/bin/env python3
"""
view_tasks.py — Render a task list for a milestone.

Usage:
    python view_tasks.py <project> <roadmap> <track> <milestone>

Output:
    Milestone name + status · done/total header
    Column-aligned task table with seq (1..n) and ← next marker
    Footer: next unblocked task
"""

import os
import re
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT

COL_SEQ    = 3
COL_STATUS = 7
MAX_TITLE  = 52


# ---------------------------------------------------------------------------
# project.json helpers
# ---------------------------------------------------------------------------

def load_project_json(project):
    pjson = os.path.join(NIMBILITY_ROOT, project, "project.json")
    if not os.path.isfile(pjson):
        return {"roadmaps": [], "tracks": {}, "milestones": {}, "tasks": {}}
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

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Parsing
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

    criteria_total = len(re.findall(r"^\s*\[[ x]\]", text, re.MULTILINE))
    criteria_done  = len(re.findall(r"^\s*\[x\]",    text, re.MULTILINE))

    return title, status, deps, criteria_total, criteria_done


def load_tasks(milestone_dir, task_order):
    """Load tasks using project.json order. Falls back to filesystem if order is empty."""
    if not os.path.isdir(milestone_dir):
        return []

    if task_order:
        slugs = task_order
    else:
        slugs = sorted([
            f.replace(".md", "")
            for f in os.listdir(milestone_dir)
            if f.endswith(".md") and not f.startswith(".")
        ])

    tasks = []
    for seq, slug in enumerate(slugs, 1):
        fpath = os.path.join(milestone_dir, f"{slug}.md")
        if not os.path.isfile(fpath):
            continue
        title, status, deps, ct, cd = parse_task_file(fpath)
        tasks.append({
            "seq":   seq,
            "slug":  slug,
            "title": title or slug,
            "status": status,
            "deps":  deps,
            "criteria_total": ct,
            "criteria_done":  cd,
        })

    return tasks


# ---------------------------------------------------------------------------
# Status rollup
# ---------------------------------------------------------------------------

def compute_status(tasks):
    statuses = [t["status"] for t in tasks]
    if not statuses:
        return "x"
    if all(s == "done" for s in statuses):
        return "done"
    if all(s in ("done", "ready") for s in statuses):
        return "ready"
    done_count = sum(1 for s in statuses if s == "done")
    if any(s in ("doing", "ready") for s in statuses) or done_count > 0:
        return "doing"
    return "pending"


# ---------------------------------------------------------------------------
# Next unblocked
# ---------------------------------------------------------------------------

def find_next(tasks):
    done_slugs = {t["slug"] for t in tasks if t["status"] == "done"}
    for t in tasks:
        if t["status"] not in ("todo", "pending"):
            continue
        if all(dep in done_slugs for dep in t["deps"]):
            return t["seq"]
    return None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def format_deps(deps):
    if not deps:
        return "—"
    return ", ".join(deps)


def render(milestone_name, tasks, oob_tasks=None):
    if oob_tasks is None:
        oob_tasks = []

    if not tasks and not oob_tasks:
        return f"{milestone_name}\n(no tasks)"

    ms_status = compute_status(tasks)
    done  = sum(1 for t in tasks + oob_tasks if t["status"] == "done")
    total = len(tasks) + len(oob_tasks)
    next_seq = find_next(tasks)

    all_for_cols = tasks + oob_tasks
    dep_strs     = [format_deps(t["deps"]) for t in all_for_cols]
    seq_dep_strs = dep_strs[:len(tasks)]
    oob_dep_strs = dep_strs[len(tasks):]

    col_title = max(5, min(MAX_TITLE, max(len(t["title"]) for t in all_for_cols))) + 2
    col_deps  = max(4, max(len(d) for d in dep_strs)) + 2

    content_w = 1 + COL_SEQ + 2 + col_title + col_deps + COL_STATUS

    right   = f"{ms_status} · {done}/{total}"
    gap     = max(1, content_w - len(milestone_name) - len(right))
    ms_line = milestone_name + " " * gap + right
    line_w  = len(ms_line)
    sep     = "─" * line_w

    col_hdr = (
        " " +
        "#".rjust(COL_SEQ) + "  " +
        "Title".ljust(col_title) +
        "Deps".ljust(col_deps) +
        "Status"
    )

    out = [ms_line, sep, col_hdr]

    for t, dep_str in zip(tasks, seq_dep_strs):
        title = t["title"]
        if len(title) > MAX_TITLE:
            title = title[:MAX_TITLE - 3] + "..."
        marker = "  ← next" if t["seq"] == next_seq else ""
        row = (
            " " +
            str(t["seq"]).rjust(COL_SEQ) + "  " +
            title.ljust(col_title) +
            dep_str.ljust(col_deps) +
            t["status"] +
            marker
        )
        out.append(row)

    if oob_tasks:
        out.append(sep)
        for t, dep_str in zip(oob_tasks, oob_dep_strs):
            title = t["title"]
            if len(title) > MAX_TITLE:
                title = title[:MAX_TITLE - 3] + "..."
            row = (
                " " +
                "·".rjust(COL_SEQ) + "  " +
                title.ljust(col_title) +
                dep_str.ljust(col_deps) +
                t["status"]
            )
            out.append(row)

    out.append(sep)

    if next_seq:
        nt = next(t for t in tasks if t["seq"] == next_seq)
        out.append(f"Next unblocked: {next_seq} — {nt['title']}")
    else:
        remaining = [t for t in tasks if t["status"] not in ("done", "ready")]
        if remaining:
            out.append("Next unblocked: none (all remaining tasks are blocked)")
        else:
            out.append("All tasks complete.")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) not in (4, 5):
        print("Usage: view_tasks.py <project> <roadmap> <track> [<milestone>]")
        sys.exit(1)

    project, roadmap, track = sys.argv[1], sys.argv[2], sys.argv[3]
    milestone = sys.argv[4] if len(sys.argv) == 5 else None

    data = load_project_json(project)

    if milestone:
        active = milestone
    else:
        m_key = f"{roadmap}/{track}"
        all_milestones = data["milestones"].get(m_key, [])
        if not all_milestones:
            oob_slugs = set(data.get("oob_milestones", {}).get(m_key, []))
            track_dir = os.path.join(NIMBILITY_ROOT, project, roadmap, track)
            if os.path.isdir(track_dir):
                all_milestones = sorted([
                    d for d in os.listdir(track_dir)
                    if os.path.isdir(os.path.join(track_dir, d)) and not d.startswith(".")
                    and d not in oob_slugs
                ])

        # Pick the active milestone: first with a "doing" task, else first not fully done,
        # else the last milestone.
        active = all_milestones[-1] if all_milestones else None
        for ms in all_milestones:
            ms_dir = os.path.join(NIMBILITY_ROOT, project, roadmap, track, ms)
            t_key = f"{roadmap}/{track}/{ms}"
            tasks = load_tasks(ms_dir, data["tasks"].get(t_key, []))
            statuses = [t["status"] for t in tasks]
            if any(s == "doing" for s in statuses):
                active = ms
                break
            if any(s != "done" for s in statuses):
                active = ms
                break

    if not active:
        print("(no milestones)")
        return

    milestone_dir = os.path.join(NIMBILITY_ROOT, project, roadmap, track, active)
    if not os.path.isdir(milestone_dir):
        print(f"Error: milestone '{active}' not found.", file=sys.stderr)
        sys.exit(1)
    t_key = f"{roadmap}/{track}/{active}"
    tasks = load_tasks(milestone_dir, data["tasks"].get(t_key, []))
    oob_slugs = sorted(data["oob_tasks"].get(t_key, []))
    oob_tasks = load_tasks(milestone_dir, oob_slugs) if oob_slugs else []
    print(render(active, tasks, oob_tasks))


if __name__ == "__main__":
    main()
