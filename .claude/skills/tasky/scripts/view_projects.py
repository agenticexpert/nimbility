#!/usr/bin/env python3
"""
view_projects.py — Render a roadmap progress table for a project.

Usage:
    python view_projects.py [<project>] [--all]

    --all  Show focus-hidden roadmaps (marked with ~).

Output:
    Project header
    Column-aligned table: # | Roadmap | Progress | Status | Tracks | Miles | Tasks
    Summary row (totals always include focus-hidden roadmaps)
"""

import argparse
import os
import re
import sys
import json
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT


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
    data.setdefault("oob_milestones", {})
    data.setdefault("oob_tasks", {})
    data.setdefault("oob_roadmaps", {})
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


def count_milestone(milestone_dir, task_order, oob_task_slugs=None):
    done = total = 0
    slugs = task_order if task_order else sorted([
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


def count_roadmap(roadmap_dir, roadmap, data):
    tracks_done = tracks_total = 0
    miles_done = miles_total = tasks_done = tasks_total = 0
    track_statuses = []

    rm_info = data["tracks"].get(roadmap, {})
    track_order = rm_info.get("order", [])
    fs_tracks = sorted([
        d for d in os.listdir(roadmap_dir)
        if os.path.isdir(os.path.join(roadmap_dir, d)) and not d.startswith(".")
    ])
    all_tracks = track_order + [t for t in fs_tracks if t not in track_order]

    for tname in all_tracks:
        tpath = os.path.join(roadmap_dir, tname)
        if not os.path.isdir(tpath):
            continue
        md, mt, td, tt, status = count_track(tpath, roadmap, tname, data)
        miles_done  += md
        miles_total += mt
        tasks_done  += td
        tasks_total += tt
        tracks_total += 1
        track_statuses.append(status)
        if status == "done":
            tracks_done += 1

    status = rollup_status(track_statuses)
    return tracks_done, tracks_total, miles_done, miles_total, tasks_done, tasks_total, status


def load_roadmaps(project):
    """Returns (seq_roadmaps, oob_roadmaps, hidden_roadmaps)."""
    project_dir = os.path.join(NIMBILITY_ROOT, project)
    if not os.path.isdir(project_dir):
        return [], [], []

    data = load_project_json(project)
    hidden_roadmaps_set, _, _ = parse_focus_hide(data)

    oob_set = set(data["oob_roadmaps"].get(project, []))
    roadmap_order = data["roadmaps"]
    fs_roadmaps = sorted([
        d for d in os.listdir(project_dir)
        if os.path.isdir(os.path.join(project_dir, d)) and not d.startswith(".")
        and d not in oob_set
    ])
    all_seq_names = roadmap_order + [r for r in fs_roadmaps if r not in roadmap_order]

    def build_roadmap(rname):
        rpath = os.path.join(project_dir, rname)
        if not os.path.isdir(rpath):
            return None
        trd, trt, md, mt, td, tt, status = count_roadmap(rpath, rname, data)
        return {
            "name":         rname,
            "tracks_done":  trd,
            "tracks_total": trt,
            "miles_done":   md,
            "miles_total":  mt,
            "tasks_done":   td,
            "tasks_total":  tt,
            "status":       status,
        }

    seq_roadmaps    = []
    hidden_roadmaps = []
    for rname in all_seq_names:
        r = build_roadmap(rname)
        if r:
            if rname in hidden_roadmaps_set:
                hidden_roadmaps.append(r)
            else:
                seq_roadmaps.append(r)

    oob_roadmaps = [r for r in (build_roadmap(n) for n in sorted(oob_set)) if r]

    return seq_roadmaps, oob_roadmaps, hidden_roadmaps


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


def render(project, roadmaps, oob_roadmaps=None, hidden_roadmaps=None, show_all=False):
    if oob_roadmaps is None:
        oob_roadmaps = []
    if hidden_roadmaps is None:
        hidden_roadmaps = []

    # Totals always include all roadmaps (true state)
    all_roadmaps_for_totals = roadmaps + oob_roadmaps + hidden_roadmaps

    if not all_roadmaps_for_totals:
        return "(no roadmaps)"

    lead_data = " "
    lead_sep  = ""
    col_seq   = 3

    max_name_len = max(len(r["name"]) for r in all_roadmaps_for_totals)
    col_roadmap  = max(8, min(37, max_name_len + 2))

    total_tasks_done = sum(r["tasks_done"]  for r in all_roadmaps_for_totals)
    total_tasks_all  = sum(r["tasks_total"] for r in all_roadmaps_for_totals)

    max_pct = max(
        [int((r["tasks_done"] / r["tasks_total"] * 100) if r["tasks_total"] > 0 else 0)
         for r in all_roadmaps_for_totals] +
        [int((total_tasks_done / total_tasks_all * 100) if total_tasks_all > 0 else 0)]
    )
    max_pct_width = len(str(max_pct))
    col_progress  = 1 + 32 + 2 + max_pct_width + 1 + 1

    col_status = 10
    col_tracks = 9
    col_miles  = 9
    col_tasks  = 9

    lines = []

    header = (
        lead_data + "#".rjust(col_seq) + "  " +
        "Roadmap".ljust(col_roadmap + 1) +
        "Progress".ljust(col_progress + 1) +
        "Status".ljust(col_status + 1) +
        "Tracks".rjust(col_tracks) + " " +
        "Miles".rjust(col_miles) + " " +
        "Tasks".rjust(col_tasks)
    )
    lines.append(header)

    top_sep = (
        lead_sep + "─" * (col_seq + 2) + "┬" +
        "─" * col_roadmap + "┬" +
        "─" * col_progress + "┬" +
        "─" * col_status + "┬" +
        "─" * col_tracks + "┬" +
        "─" * col_miles + "┬" +
        "─" * col_tasks
    )
    lines.append(top_sep)

    def data_line(seq_cell, r):
        bar, pct = render_progress_bar(r["tasks_done"], r["tasks_total"])
        name = r["name"]
        if len(name) > col_roadmap - 2:
            name = name[:col_roadmap - 5] + "..."
        roadmap_cell  = f" {name}".ljust(col_roadmap)
        progress_cell = f" {bar}  {pct:>{max_pct_width}}% "
        status_cell   = f" {r['status']}".ljust(col_status)
        tracks_cell   = f"{r['tracks_done']}/{r['tracks_total']}".rjust(col_tracks - 1) + " "
        miles_cell    = f"{r['miles_done']}/{r['miles_total']}".rjust(col_miles - 1) + " "
        tasks_cell    = f"{r['tasks_done']}/{r['tasks_total']}".rjust(col_tasks)
        return (
            lead_data + seq_cell + " │" +
            roadmap_cell + "│" +
            progress_cell + "│" +
            status_cell + "│" +
            tracks_cell + "│" +
            miles_cell + "│" +
            tasks_cell
        )

    w = len(str(len(roadmaps))) if roadmaps else 1
    for i, r in enumerate(roadmaps):
        seq_cell = f"{i + 1:0{w}d}".rjust(col_seq)
        lines.append(data_line(seq_cell, r))

    mid_sep = (
        lead_sep + "─" * (col_seq + 2) + "┼" +
        "─" * col_roadmap + "┼" +
        "─" * col_progress + "┼" +
        "─" * col_status + "┼" +
        "─" * col_tracks + "┼" +
        "─" * col_miles + "┼" +
        "─" * col_tasks
    )
    bottom_sep = (
        lead_sep + "─" * (col_seq + 2) + "┴" +
        "─" * col_roadmap + "┴" +
        "─" * col_progress + "┴" +
        "─" * col_status + "┴" +
        "─" * col_tracks + "┴" +
        "─" * col_miles + "┴" +
        "─" * col_tasks
    )

    if oob_roadmaps:
        lines.append(mid_sep)
        for r in oob_roadmaps:
            lines.append(data_line("·".rjust(col_seq), r))

    if show_all and hidden_roadmaps:
        lines.append(mid_sep)
        for r in hidden_roadmaps:
            lines.append(data_line("~".rjust(col_seq), r))

    lines.append(bottom_sep)

    summary_bar, summary_pct = render_progress_bar(total_tasks_done, total_tasks_all)
    total_tracks_done = sum(r["tracks_done"]  for r in all_roadmaps_for_totals)
    total_tracks_all  = sum(r["tracks_total"] for r in all_roadmaps_for_totals)
    total_miles_done  = sum(r["miles_done"]   for r in all_roadmaps_for_totals)
    total_miles_all   = sum(r["miles_total"]  for r in all_roadmaps_for_totals)

    space_before   = col_roadmap - 3
    table_width    = (1 + col_seq + 2 + col_roadmap + 1 + col_progress + 1 +
                      col_status + 1 + col_tracks + 1 + col_miles + 1 + col_tasks)
    summary_prefix = lead_data + " " * space_before + f"Progress: {summary_bar}  {summary_pct:>{max_pct_width}}% "
    remaining      = table_width - len(summary_prefix) - col_tracks - 1 - col_miles - 1 - col_tasks
    summary_line   = (
        summary_prefix +
        " " * remaining +
        f"{total_tracks_done}/{total_tracks_all}".rjust(col_tracks - 1) + " " +
        " " + f"{total_miles_done}/{total_miles_all}".rjust(col_miles - 1) + " " +
        " " + f"{total_tasks_done}/{total_tasks_all}".rjust(col_tasks)
    )
    lines.append(summary_line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project", nargs="?", default=None)
    parser.add_argument("--all", dest="show_all", action="store_true", default=False,
                        help="Show focus-hidden roadmaps (marked with ~).")
    args = parser.parse_args()

    if args.project:
        projects = [args.project]
    else:
        if not os.path.isdir(NIMBILITY_ROOT):
            print("No projects found.")
            return
        projects = sorted([
            d for d in os.listdir(NIMBILITY_ROOT)
            if os.path.isdir(os.path.join(NIMBILITY_ROOT, d)) and not d.startswith(".")
        ])

    for project in projects:
        seq_roadmaps, oob_roadmaps, hidden_roadmaps = load_roadmaps(project)
        print()
        print(f"Project: {project}")
        print()
        print()
        print(render(project, seq_roadmaps, oob_roadmaps, hidden_roadmaps, show_all=args.show_all))
        print()


if __name__ == "__main__":
    main()
