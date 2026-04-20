#!/usr/bin/env python3
"""
view_milestones.py — Render a Gantt chart for all milestones in a roadmap.

Usage:
    python view_milestones.py <project> <roadmap> [<track>] [--all]

    --all  Show focus-hidden milestones (marked with ~, no Gantt column).

Milestones from all tracks are listed globally numbered in track order.
Each milestone occupies its own column slot. Status is derived from task rollup.
Totals always include focus-hidden milestones (true state).
"""

import os
import re
import sys
import json
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT
FILL_COUNT     = 20
LEGEND         = " █ done  ▓ doing  ▒ paused  ░ pending"


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
    data.setdefault("milestone_slots", {})
    data.setdefault("milestone_deps", {})
    data.setdefault("focus", {})
    return data


def parse_focus_hide(data):
    """Returns (hidden_roadmaps: set, hidden_tracks: dict, hidden_milestones: dict)"""
    hide = data.get("focus", {}).get("hide", {})
    if not isinstance(hide, dict):
        return set(), {}, {}
    hidden_roadmaps   = set(hide.get("roadmaps", []))
    hidden_tracks     = {k: set(v) for k, v in hide.get("tracks", {}).items()}
    hidden_milestones = {k: set(v) for k, v in hide.get("milestones", {}).items()}
    return hidden_roadmaps, hidden_tracks, hidden_milestones


# ---------------------------------------------------------------------------
# Tree walking
# ---------------------------------------------------------------------------

def read_task_status(path):
    with open(path) as f:
        for line in f:
            m = re.match(r"^Status:\s*(.+)$", line.strip())
            if m:
                return m.group(1).strip().lower()
    return "x"


def rollup_status(statuses):
    if not statuses:
        return "x"
    statuses = [s.lower() for s in statuses]
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
    if any(s in ("pending", "todo") for s in non_x):
        return "pending"
    return "x"


def topo_sort_tracks(slugs, deps):
    in_degree = {s: 0 for s in slugs}
    graph     = {s: [] for s in slugs}
    for slug in slugs:
        for dep in deps.get(slug, []):
            if dep in in_degree:
                in_degree[slug] += 1
                graph[dep].append(slug)
    queue  = sorted(s for s in slugs if in_degree[s] == 0)
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in sorted(graph[node]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    result.extend(s for s in slugs if s not in result)
    return result


def load_milestone_stats(track_dir, roadmap, track_name, mslug, data):
    mpath = os.path.join(track_dir, mslug)
    if not os.path.isdir(mpath):
        return None
    t_key = f"{roadmap}/{track_name}/{mslug}"
    task_order = data["tasks"].get(t_key, [])
    if not task_order:
        task_order = sorted([
            f.replace(".md", "")
            for f in os.listdir(mpath)
            if f.endswith(".md") and not f.startswith(".")
        ])
    oob_task_slugs = data["oob_tasks"].get(t_key, [])
    all_slugs = list(task_order) + [s for s in oob_task_slugs if s not in task_order]
    done = total = 0
    task_statuses = []
    for slug in all_slugs:
        fpath = os.path.join(mpath, f"{slug}.md")
        if os.path.isfile(fpath):
            status = read_task_status(fpath)
            task_statuses.append(status)
            total += 1
            if status == "done":
                done += 1
    return {
        "name":   mslug,
        "track":  track_name,
        "status": rollup_status(task_statuses),
        "done":   done,
        "total":  total,
    }


def load_all_milestones(project, roadmap, track_filter=None):
    """Returns (seq_milestones, oob_milestones, hidden_milestones)."""
    data = load_project_json(project)
    _, _, hidden_milestones_dict = parse_focus_hide(data)

    roadmap_dir = os.path.join(NIMBILITY_ROOT, project, roadmap)
    if not os.path.isdir(roadmap_dir):
        return [], [], []

    rm_info = data["tracks"].get(roadmap, {})
    track_order = rm_info.get("order", [])
    deps_dict   = rm_info.get("deps", {})
    fs_tracks   = sorted([
        d for d in os.listdir(roadmap_dir)
        if os.path.isdir(os.path.join(roadmap_dir, d)) and not d.startswith(".")
    ])
    combined   = track_order + [t for t in fs_tracks if t not in track_order]
    all_tracks = topo_sort_tracks(combined, deps_dict)

    milestones        = []
    oob_milestones    = []
    hidden_milestones = []
    global_seq = 0

    for track_name in all_tracks:
        if track_filter and track_name != track_filter:
            continue
        track_dir = os.path.join(roadmap_dir, track_name)
        if not os.path.isdir(track_dir):
            continue

        m_key = f"{roadmap}/{track_name}"
        ms_order   = data["milestones"].get(m_key, [])
        oob_slugs  = set(data.get("oob_milestones", {}).get(m_key, []))
        hidden_set = hidden_milestones_dict.get(m_key, set())

        if not ms_order:
            ms_order = sorted([
                d for d in os.listdir(track_dir)
                if os.path.isdir(os.path.join(track_dir, d)) and not d.startswith(".")
                and d not in oob_slugs
            ])

        for mslug in ms_order:
            global_seq += 1
            entry = load_milestone_stats(track_dir, roadmap, track_name, mslug, data)
            if entry:
                entry["seq"] = global_seq
                slot_key = f"{roadmap}/{track_name}/{mslug}"
                declared = data["milestone_slots"].get(slot_key)
                entry["slots"] = declared if declared else [global_seq]
                if mslug in hidden_set:
                    hidden_milestones.append(entry)
                else:
                    milestones.append(entry)

        for mslug in sorted(oob_slugs):
            entry = load_milestone_stats(track_dir, roadmap, track_name, mslug, data)
            if entry:
                slot_key = f"{roadmap}/{track_name}/{mslug}"
                entry["slots"] = data["milestone_slots"].get(slot_key, [])
                oob_milestones.append(entry)

    return milestones, oob_milestones, hidden_milestones


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def milestone_bar(status, done, total, slot_idx, num_slots):
    total_chars = 5 * num_slots
    slot_start  = slot_idx * 5
    if status == "done":
        return "█████"
    if total > 0 and done > 0:
        filled    = math.floor(done / total * total_chars)
        fill_char = "▒" if status == "paused" else "▓"
        return "".join("█" if (slot_start + i) < filled else fill_char for i in range(5))
    if status in ("doing", "ready"):
        return "▓▓▓▓▓"
    if status == "paused":
        return "▒▒▒▒▒"
    return "░░░░░"


def render(roadmap, milestones, oob_milestones=None, hidden_milestones=None, show_all=False):
    if not milestones and not (oob_milestones or []) and not (hidden_milestones or []):
        return "(no milestones)"
    if oob_milestones is None:
        oob_milestones = []
    if hidden_milestones is None:
        hidden_milestones = []

    n = len(milestones)
    seq_w = len(str(n)) if n > 0 else 1

    max_name = max((len(m["name"]) for m in milestones), default=4)
    label_w  = seq_w + 2 + max_name + 3

    # Totals include all milestones (true state)
    all_miles   = milestones + oob_milestones + hidden_milestones
    max_val     = max((max(m["done"], m["total"]) for m in milestones), default=0)
    trailing_w  = max(6, len(str(max_val)) * 2 + 2)

    INDENT = " "
    DASHES = label_w - len(INDENT)

    # Find active milestone
    active_seq = milestones[-1]["seq"] if milestones else None
    found = False
    for m in milestones:
        if m["status"] in ("doing", "ready"):
            active_seq = m["seq"]
            found = True
            break
    if not found:
        for m in milestones:
            if m["done"] > 0 and m["status"] != "done":
                active_seq = m["seq"]
                found = True
                break
    if not found:
        for m in milestones:
            if m["status"] not in ("done", "x"):
                active_seq = m["seq"]
                break

    out = []
    out.append(f"  {roadmap}")
    out.append("")

    # Header: phase numbers
    if n > 0:
        header = INDENT + "Milestone" + " " * (label_w - len(INDENT) - len("Milestone"))
        for p in range(1, n + 1):
            ps = str(p)
            header += ps + " " * (6 - len(ps))
        out.append(header.rstrip())
        out.append("")
        out.append(INDENT + "─" * DASHES + ("┬─────") * n + "┬" + "─" * trailing_w)
    else:
        out.append(INDENT + "Milestone")
        out.append("")
        out.append(INDENT + "─" * DASHES + "┬" + "─" * trailing_w)

    for m in milestones:
        seq_str = str(m["seq"]).zfill(seq_w)
        id_name = f" {seq_str}  {m['name']}"
        label   = INDENT + id_name + " " * (label_w - len(INDENT) - len(id_name))

        slots     = sorted(m["slots"])
        slots_set = set(slots)
        num_slots = len(slots)
        content = ""
        for p in range(1, n + 1):
            if p in slots_set:
                slot_idx = slots.index(p)
                bar = milestone_bar(m["status"], m["done"], m["total"], slot_idx, num_slots)
            else:
                bar = "     "
            content += f"│{bar}"
        content += "│"

        count    = f"{m['done']}/{m['total']}"
        trailing = count.rjust(trailing_w)
        out.append(label + content + trailing)

    # Separator after sequenced rows
    needs_bottom = True
    if oob_milestones or (show_all and hidden_milestones):
        out.append(INDENT + "─" * DASHES + ("┼─────") * n + "┼" + "─" * trailing_w)
        needs_bottom = False

    # OOB milestones
    if oob_milestones:
        for m in oob_milestones:
            name = m['name']
            if len(name) > max_name:
                name = name[:max_name - 1] + "…"
            oob_label = f"    {name}"
            label = INDENT + oob_label + " " * (label_w - len(INDENT) - len(oob_label))
            slots     = sorted(m["slots"])
            slots_set = set(slots)
            num_slots = len(slots)
            content = ""
            for p in range(1, n + 1):
                if p in slots_set:
                    slot_idx = slots.index(p)
                    bar = milestone_bar(m["status"], m["done"], m["total"], slot_idx, num_slots)
                else:
                    bar = "     "
                content += f"│{bar}"
            content += "│"
            count    = f"{m['done']}/{m['total']}"
            trailing = count.rjust(trailing_w)
            out.append(label + content + trailing)
        if show_all and hidden_milestones:
            out.append(INDENT + "─" * DASHES + ("┼─────") * n + "┼" + "─" * trailing_w)
        else:
            out.append(INDENT + "─" * DASHES + ("┴─────") * n + "┴" + "─" * trailing_w)
            needs_bottom = False

    # Hidden milestones (only when --all)
    if show_all and hidden_milestones:
        for m in hidden_milestones:
            name = m['name']
            if len(name) > max_name:
                name = name[:max_name - 1] + "…"
            h_label = f"~   {name}"
            label = INDENT + h_label + " " * (label_w - len(INDENT) - len(h_label))
            # No Gantt columns — all blank
            content = ("│     " * n) + "│"
            count    = f"{m['done']}/{m['total']}"
            trailing = count.rjust(trailing_w)
            out.append(label + content + trailing)
        out.append(INDENT + "─" * DASHES + ("┴─────") * n + "┴" + "─" * trailing_w)
        needs_bottom = False

    if needs_bottom:
        out.append(INDENT + "─" * DASHES + ("┴─────") * n + "┴" + "─" * trailing_w)

    # Progress bar (totals include all)
    total_done  = sum(m["done"]  for m in all_miles)
    total_tasks = sum(m["total"] for m in all_miles)

    if total_tasks > 0:
        filled = math.floor(total_done / total_tasks * FILL_COUNT)
        pct    = math.floor(total_done / total_tasks * 100)
    else:
        filled = 0
        pct    = 0

    bar_str   = "█" * filled + "░" * (FILL_COUNT - filled)
    count_str = f"{total_done}/{total_tasks}"

    if n >= 3:
        line_w     = len(INDENT) + DASHES + 6 * n + 1 + trailing_w
        prog_bar   = f"[{bar_str}]"
        col2       = len(INDENT) + DASHES + 6
        col3       = len(INDENT) + DASHES + 12
        bar_start  = col2 - len(prog_bar) + 1
        pct_str    = f"{pct}%"
        pct_start  = col3 - len(pct_str) + 1
        gap        = line_w - col3 - 1 - len(count_str)
        out.append(" " * bar_start + prog_bar + " " * (pct_start - col2 - 1) + pct_str + " " * max(1, gap) + count_str)
    else:
        out.append(INDENT + " " * (DASHES + 6 * n + 1) + count_str.rjust(trailing_w))
    out.append("")
    out.append(LEGEND)
    out.append("")

    # Status line
    active = next((m for m in milestones if m["seq"] == active_seq), None) if active_seq else None
    done_count = sum(1 for m in milestones if m["status"] == "done")
    if active:
        if done_count > 0:
            done_range = f"M{str(milestones[0]['seq']).zfill(seq_w)}"
            if done_count > 1:
                done_range = f"M{str(milestones[0]['seq']).zfill(seq_w)}–M{str(milestones[done_count - 1]['seq']).zfill(seq_w)}"
            out.append(f" {done_range} complete. Currently in M{str(active['seq']).zfill(seq_w)} {active['name']} at {active['done']}/{active['total']} tasks.")
        else:
            out.append(f" Currently in M{str(active['seq']).zfill(seq_w)} {active['name']} at {active['done']}/{active['total']} tasks.")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("roadmap")
    parser.add_argument("track", nargs="?", default=None, help="Filter by track (optional)")
    parser.add_argument("--all", dest="show_all", action="store_true", default=False,
                        help="Show focus-hidden milestones (marked with ~).")
    args = parser.parse_args()

    milestones, oob_milestones, hidden_milestones = load_all_milestones(args.project, args.roadmap, args.track)
    title = f"{args.roadmap}/{args.track}" if args.track else args.roadmap
    print(render(title, milestones, oob_milestones, hidden_milestones, show_all=args.show_all))


if __name__ == "__main__":
    main()
