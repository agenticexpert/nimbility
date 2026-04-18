#!/usr/bin/env python3
"""
view_tracks.py — Render a track progress table for a roadmap.

Usage:
    python view_tracks.py <project> <roadmap> [--all]

    --all  Show focus-hidden tracks (marked with ~).

Output:
    Roadmap header
    Column-aligned table: # | Track | Progress | Status | Miles | Tasks
    Summary row (totals always include focus-hidden tracks)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT


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
    data.setdefault("track_slots", {})
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


def read_task_status(path):
    with open(path) as f:
        for line in f:
            m = re.match(r"^Status:\s*(.+)$", line.strip())
            if m:
                return m.group(1).strip().lower()
    return "x"


def count_milestone(milestone_dir, task_order, oob_task_slugs=None):
    done, total = 0, 0
    if task_order:
        slugs = task_order
    else:
        slugs = sorted([
            f.replace(".md", "")
            for f in os.listdir(milestone_dir)
            if f.endswith(".md") and not f.startswith(".")
        ])
    if oob_task_slugs:
        slugs = list(slugs) + [s for s in oob_task_slugs if s not in slugs]
    for slug in slugs:
        fpath = os.path.join(milestone_dir, f"{slug}.md")
        if os.path.isfile(fpath):
            status = read_task_status(fpath)
            total += 1
            if status == "done":
                done += 1
    return done, total


def count_track(track_dir, roadmap, track, data):
    miles_done = miles_total = tasks_done = tasks_total = 0
    milestone_statuses = []

    m_key = f"{roadmap}/{track}"
    oob_slugs = set(data.get("oob_milestones", {}).get(m_key, []))
    ms_order = data["milestones"].get(m_key, [])
    if not ms_order:
        ms_order = sorted([
            d for d in os.listdir(track_dir)
            if os.path.isdir(os.path.join(track_dir, d)) and not d.startswith(".")
            and d not in oob_slugs
        ])
    all_slugs = list(ms_order) + sorted(oob_slugs)

    for mslug in all_slugs:
        mpath = os.path.join(track_dir, mslug)
        if not os.path.isdir(mpath):
            continue

        t_key = f"{roadmap}/{track}/{mslug}"
        task_order = data["tasks"].get(t_key, [])
        oob_task_slugs = data["oob_tasks"].get(t_key, [])
        td, tt = count_milestone(mpath, task_order, oob_task_slugs)
        tasks_done  += td
        tasks_total += tt
        miles_total += 1

        if tt == 0:
            ms = "x"
        elif td == tt:
            ms = "done"
        elif td > 0:
            ms = "doing"
        else:
            ms = "pending"
        milestone_statuses.append(ms)
        if ms == "done":
            miles_done += 1

    status = rollup_status(milestone_statuses)
    return miles_done, miles_total, tasks_done, tasks_total, status


def topo_sort_tracks(tracks, deps):
    slug_to_track = {t["name"]: t for t in tracks}
    slugs = [t["name"] for t in tracks]
    in_degree = {s: 0 for s in slugs}
    graph = {s: [] for s in slugs}
    for slug in slugs:
        for dep in deps.get(slug, []):
            if dep in in_degree:
                in_degree[slug] += 1
                graph[dep].append(slug)
    queue = sorted(s for s in slugs if in_degree[s] == 0)
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in sorted(graph[node]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    remaining = sorted(s for s in slugs if s not in result)
    result.extend(remaining)
    return [slug_to_track[s] for s in result if s in slug_to_track]


def load_tracks(project, roadmap):
    """Returns (seq_tracks, oob_tracks, hidden_tracks)."""
    roadmap_dir = os.path.join(NIMBILITY_ROOT, project, roadmap)
    if not os.path.isdir(roadmap_dir):
        return [], [], []

    data = load_project_json(project)
    _, hidden_tracks_dict, _ = parse_focus_hide(data)
    hidden_track_set = hidden_tracks_dict.get(roadmap, set())

    rm_info = data["tracks"].get(roadmap, {})
    track_order = rm_info.get("order", [])
    deps_dict = rm_info.get("deps", {})
    oob_track_slugs = set(data["oob_tracks"].get(roadmap, []))

    fs_tracks = sorted([
        d for d in os.listdir(roadmap_dir)
        if os.path.isdir(os.path.join(roadmap_dir, d)) and not d.startswith(".")
        and d not in oob_track_slugs
    ])
    all_seq_names = track_order + [t for t in fs_tracks if t not in track_order]

    def build_track(tname, seq):
        tpath = os.path.join(roadmap_dir, tname)
        if not os.path.isdir(tpath):
            return None
        md, mt, td, tt, status = count_track(tpath, roadmap, tname, data)
        m_key = f"{roadmap}/{tname}"
        slot_key = f"{roadmap}/{tname}"
        slots = data["track_slots"].get(slot_key) or [seq]
        return {
            "name":           tname,
            "seq":            seq,
            "slots":          slots,
            "miles_done":     md,
            "miles_total":    mt,
            "tasks_done":     td,
            "tasks_total":    tt,
            "status":         status,
            "oob_milestones": data.get("oob_milestones", {}).get(m_key, []),
        }

    seq_tracks    = []
    hidden_tracks = []
    seq_num = 0
    for tname in all_seq_names:
        seq_num += 1
        entry = build_track(tname, seq_num)
        if entry:
            if tname in hidden_track_set:
                hidden_tracks.append(entry)
            else:
                seq_tracks.append(entry)

    oob_raw = []
    for tname in sorted(oob_track_slugs):
        entry = build_track(tname, 0)
        if entry:
            oob_raw.append(entry)

    return topo_sort_tracks(seq_tracks, deps_dict), oob_raw, hidden_tracks


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_progress_bar(done, total, width=30):
    if total == 0:
        filled = 0
    else:
        filled = int((done / total) * width)
    bar = "[" + "█" * filled + "░" * (width - filled) + "]"
    pct = int((done / total) * 100) if total > 0 else 0
    return bar, pct


def render(project, roadmap, tracks, oob_tracks=None, hidden_tracks=None, show_all=False):
    if oob_tracks is None:
        oob_tracks = []
    if hidden_tracks is None:
        hidden_tracks = []

    # Totals always include all tracks (true state)
    all_tracks_for_totals = tracks + oob_tracks + hidden_tracks

    if not all_tracks_for_totals:
        return "(no tracks)"

    lead_data = " "
    lead_sep  = ""
    col_seq   = 3

    max_name_len = max(len(t["name"]) for t in all_tracks_for_totals)
    col_track = max(8, min(37, max_name_len + 2))

    total_tasks_done = sum(t["tasks_done"]  for t in all_tracks_for_totals)
    total_tasks_all  = sum(t["tasks_total"] for t in all_tracks_for_totals)

    max_pct = max(
        [int((t["tasks_done"] / t["tasks_total"] * 100) if t["tasks_total"] > 0 else 0)
         for t in all_tracks_for_totals] +
        [int((total_tasks_done / total_tasks_all * 100) if total_tasks_all > 0 else 0)]
    )
    max_pct_width = len(str(max_pct))
    col_progress = 1 + 32 + 2 + max_pct_width + 1 + 1

    col_status = 10
    col_miles  = 9
    col_tasks  = 9

    lines = []

    header = (
        lead_data + "#".rjust(col_seq) + "  " +
        "Track".ljust(col_track + 1) +
        "Progress".ljust(col_progress + 1) +
        "Status".ljust(col_status + 1) +
        "Miles".rjust(col_miles) + " " +
        "Tasks".rjust(col_tasks)
    )
    lines.append(header)

    top_sep = (
        lead_sep + "─" * (col_seq + 2) + "┬" +
        "─" * col_track + "┬" +
        "─" * col_progress + "┬" +
        "─" * col_status + "┬" +
        "─" * col_miles + "┬" +
        "─" * col_tasks
    )
    lines.append(top_sep)

    def data_line(seq_cell, t):
        bar, pct = render_progress_bar(t["tasks_done"], t["tasks_total"])
        name = t["name"]
        if len(name) > col_track - 2:
            name = name[:col_track - 5] + "..."
        track_cell    = f" {name}".ljust(col_track)
        progress_cell = f" {bar}  {pct:>{max_pct_width}}% "
        status_cell   = f" {t['status']}".ljust(col_status)
        miles_cell    = f"{t['miles_done']}/{t['miles_total']}".rjust(col_miles - 1) + " "
        tasks_cell    = f"{t['tasks_done']}/{t['tasks_total']}".rjust(col_tasks)
        return (
            lead_data + seq_cell + " │" +
            track_cell + "│" +
            progress_cell + "│" +
            status_cell + "│" +
            miles_cell + "│" +
            tasks_cell
        )

    w = len(str(len(tracks))) if tracks else 1
    for i, t in enumerate(tracks):
        seq_cell = f"{i + 1:0{w}d}".rjust(col_seq)
        lines.append(data_line(seq_cell, t))

    mid_sep = (
        lead_sep + "─" * (col_seq + 2) + "┼" +
        "─" * col_track + "┼" +
        "─" * col_progress + "┼" +
        "─" * col_status + "┼" +
        "─" * col_miles + "┼" +
        "─" * col_tasks
    )
    bottom_sep = (
        lead_sep + "─" * (col_seq + 2) + "┴" +
        "─" * col_track + "┴" +
        "─" * col_progress + "┴" +
        "─" * col_status + "┴" +
        "─" * col_miles + "┴" +
        "─" * col_tasks
    )

    if oob_tracks:
        lines.append(mid_sep)
        for t in oob_tracks:
            lines.append(data_line("·".rjust(col_seq), t))

    if show_all and hidden_tracks:
        lines.append(mid_sep)
        for t in hidden_tracks:
            lines.append(data_line("~".rjust(col_seq), t))

    lines.append(bottom_sep)

    summary_bar, summary_pct = render_progress_bar(total_tasks_done, total_tasks_all)
    total_miles_done = sum(t["miles_done"]  for t in all_tracks_for_totals)
    total_miles_all  = sum(t["miles_total"] for t in all_tracks_for_totals)

    space_before   = col_track - 3
    table_width    = (1 + col_seq + 2 + col_track + 1 + col_progress + 1 +
                      col_status + 1 + col_miles + 1 + col_tasks)
    summary_prefix = lead_data + " " * space_before + f"Progress: {summary_bar}  {summary_pct:>{max_pct_width}}% "
    remaining      = table_width - len(summary_prefix) - col_miles - 1 - col_tasks
    summary_line   = (
        summary_prefix +
        " " * remaining +
        f"{total_miles_done}/{total_miles_all}".rjust(col_miles - 1) + " " +
        " " + f"{total_tasks_done}/{total_tasks_all}".rjust(col_tasks)
    )
    lines.append(summary_line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("roadmap")
    parser.add_argument("--all", dest="show_all", action="store_true", default=False,
                        help="Show focus-hidden tracks (marked with ~).")
    args = parser.parse_args()

    tracks, oob_tracks, hidden_tracks = load_tracks(args.project, args.roadmap)

    print()
    print(f"Roadmap: {args.project}/{args.roadmap}")
    print()
    print()
    print(render(args.project, args.roadmap, tracks, oob_tracks, hidden_tracks, show_all=args.show_all))


if __name__ == "__main__":
    main()
