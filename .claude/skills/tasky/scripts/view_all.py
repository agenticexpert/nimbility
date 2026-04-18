#!/usr/bin/env python3
"""
view_all.py — Render the full project hierarchy as a tree.

Usage:
    python view_all.py [--status <statuses>] [--hide <types>] [--all]

    --status  Comma-separated statuses to filter all row types by. Rows are shown
              only if their own status matches or any descendant matches.
              Use "all" to show every row including tasks.
              Default: no filter (all rows shown, no tasks expanded).
              Example: --status ready,doing,paused

    --hide    Comma-separated row types to suppress when the parent is done.
              Values: tasks, milestones, tracks, roadmaps
              Use "none" to disable all hiding.
              Default: milestones
              Example: --hide milestones,tasks

    --all     Show focus-hidden roadmaps, tracks, and milestones (marked with ~).

Output:
    Tree rows with 2-space connectors, progress bar, status, milestones done/total,
    tasks done/total. Seq column (1..n within parent) replaces ID.
"""

import argparse
import json
import os
import re

ALL_STATUSES = {"ready", "doing", "paused", "pending", "done", "x"}

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasky_config import NIMBILITY_ROOT

NAME_WIDTH   = 40
BAR_WIDTH    = 30
STATUS_WIDTH = 9
COUNTS_WIDTH = 7   # "ddd/ttt"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def read_task_status(path):
    with open(path) as f:
        for line in f:
            m = re.match(r"^Status:\s*(.+)$", line.strip())
            if m:
                return m.group(1).strip().lower()
    return "x"


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
    data.setdefault("focus", {})
    return data


def parse_focus_hide(data):
    """Parse focus.hide from project.json.

    Returns:
        hidden_roadmaps:  set of roadmap slugs
        hidden_tracks:    dict[roadmap -> set of track slugs]
        hidden_milestones: dict["roadmap/track" -> set of milestone slugs]
    """
    hide = data.get("focus", {}).get("hide", {})
    if not isinstance(hide, dict):
        return set(), {}, {}
    hidden_roadmaps   = set(hide.get("roadmaps", []))
    hidden_tracks     = {k: set(v) for k, v in hide.get("tracks", {}).items()}
    hidden_milestones = {k: set(v) for k, v in hide.get("milestones", {}).items()}
    return hidden_roadmaps, hidden_tracks, hidden_milestones


# ---------------------------------------------------------------------------
# Track topo-sort
# ---------------------------------------------------------------------------

def topo_sort_tracks(tracks, deps):
    slug_to_track = {t["slug"]: t for t in tracks}
    slugs = [t["slug"] for t in tracks]
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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all():
    if not os.path.isdir(NIMBILITY_ROOT):
        return []

    projects = []
    pi = 0
    for pname in sorted(os.listdir(NIMBILITY_ROOT)):
        ppath = os.path.join(NIMBILITY_ROOT, pname)
        if not os.path.isdir(ppath) or pname.startswith("."):
            continue

        data = load_project_json(pname)
        pi += 1
        hidden_roadmaps_set, hidden_tracks_dict, hidden_milestones_dict = parse_focus_hide(data)

        roadmap_order   = data["roadmaps"]
        oob_roadmap_set = set(data["oob_roadmaps"].get(pname, []))
        fs_roadmaps     = sorted([
            d for d in os.listdir(ppath)
            if os.path.isdir(os.path.join(ppath, d)) and not d.startswith(".") and d != "project.json"
        ])
        ordered_roadmaps  = roadmap_order + [r for r in fs_roadmaps if r not in roadmap_order and r not in oob_roadmap_set]
        ordered_roadmaps += sorted(oob_roadmap_set)

        roadmaps = []
        ri = 0
        for rname in ordered_roadmaps:
            rpath = os.path.join(ppath, rname)
            if not os.path.isdir(rpath):
                continue
            is_oob_rm = rname in oob_roadmap_set
            if not is_oob_rm:
                ri += 1

            rm_info       = data["tracks"].get(rname, {})
            track_order   = rm_info.get("order", [])
            deps_dict     = rm_info.get("deps", {})
            oob_track_set = set(data["oob_tracks"].get(rname, []))
            fs_tracks     = sorted([
                d for d in os.listdir(rpath)
                if os.path.isdir(os.path.join(rpath, d)) and not d.startswith(".")
            ])
            all_tracks  = track_order + [t for t in fs_tracks if t not in track_order and t not in oob_track_set]
            all_tracks += sorted(oob_track_set)

            raw_tracks = []
            ti_seq = 0
            for tname in all_tracks:
                tpath = os.path.join(rpath, tname)
                if not os.path.isdir(tpath):
                    continue

                m_key      = f"{rname}/{tname}"
                ms_order   = data["milestones"].get(m_key, [])
                oob_slugs  = set(data.get("oob_milestones", {}).get(m_key, []))
                hidden_ms  = hidden_milestones_dict.get(m_key, set())
                fs_milestones = sorted([
                    d for d in os.listdir(tpath)
                    if os.path.isdir(os.path.join(tpath, d)) and not d.startswith(".")
                    and d not in oob_slugs
                ])
                sequenced = [m for m in ms_order if m not in oob_slugs] + [m for m in fs_milestones if m not in ms_order]
                oob_list  = sorted(oob_slugs)

                def load_milestone(mslug, is_oob, _hidden_ms=hidden_ms):
                    mpath = os.path.join(tpath, mslug)
                    if not os.path.isdir(mpath):
                        return None
                    t_key        = f"{rname}/{tname}/{mslug}"
                    task_order   = data["tasks"].get(t_key, [])
                    oob_task_slugs = data["oob_tasks"].get(t_key, [])
                    fs_task_files = sorted([
                        f.replace(".md", "")
                        for f in os.listdir(mpath)
                        if f.endswith(".md") and not f.startswith(".")
                    ])
                    all_task_slugs  = task_order + [t for t in fs_task_files if t not in task_order]
                    all_task_slugs += [s for s in oob_task_slugs if s not in all_task_slugs]
                    tasks = []
                    for seq, tslug in enumerate(all_task_slugs, 1):
                        fpath = os.path.join(mpath, f"{tslug}.md")
                        if not os.path.isfile(fpath):
                            continue
                        status = read_task_status(fpath)
                        tasks.append({"seq": seq, "slug": tslug, "status": status})
                    td = sum(1 for t in tasks if t["status"] == "done")
                    tt = len(tasks)
                    ms = "x" if tt == 0 else ("done" if td == tt else ("doing" if td > 0 else "pending"))
                    return {"slug": mslug, "tasks_done": td, "tasks_total": tt,
                            "status": ms, "tasks": tasks, "oob": is_oob,
                            "focus_hidden": mslug in _hidden_ms}

                milestones = []
                for mslug in sequenced:
                    entry = load_milestone(mslug, False)
                    if entry:
                        milestones.append(entry)
                for mslug in oob_list:
                    entry = load_milestone(mslug, True)
                    if entry:
                        milestones.append(entry)

                md = sum(1 for m in milestones if m["status"] == "done")
                mt = len(milestones)
                td = sum(m["tasks_done"] for m in milestones)
                tt = sum(m["tasks_total"] for m in milestones)
                is_oob_tk = tname in oob_track_set
                if not is_oob_tk:
                    ti_seq += 1
                raw_tracks.append({
                    "slug": tname,
                    "miles_done": md, "miles_total": mt,
                    "tasks_done": td, "tasks_total": tt,
                    "status": rollup([m["status"] for m in milestones]),
                    "milestones": milestones,
                    "oob": is_oob_tk,
                    "focus_hidden": tname in hidden_tracks_dict.get(rname, set()),
                })

            seq_tracks    = [t for t in raw_tracks if not t["oob"]]
            oob_tracks_list = [t for t in raw_tracks if t["oob"]]
            tracks = topo_sort_tracks(seq_tracks, deps_dict) + oob_tracks_list
            seq_i = 0
            for t in tracks:
                if not t["oob"]:
                    seq_i += 1
                    t["seq"] = seq_i
                else:
                    t["seq"] = 0

            md = sum(t["miles_done"] for t in tracks)
            mt = sum(t["miles_total"] for t in tracks)
            td = sum(t["tasks_done"] for t in tracks)
            tt = sum(t["tasks_total"] for t in tracks)
            roadmaps.append({
                "name": rname, "seq": ri,
                "miles_done": md, "miles_total": mt,
                "tasks_done": td, "tasks_total": tt,
                "status": rollup([t["status"] for t in tracks]),
                "tracks": tracks,
                "oob": is_oob_rm,
                "focus_hidden": rname in hidden_roadmaps_set,
            })

        md = sum(r["miles_done"] for r in roadmaps)
        mt = sum(r["miles_total"] for r in roadmaps)
        td = sum(r["tasks_done"] for r in roadmaps)
        tt = sum(r["tasks_total"] for r in roadmaps)
        projects.append({
            "name": pname, "seq": pi,
            "miles_done": md, "miles_total": mt,
            "tasks_done": td, "tasks_total": tt,
            "status": rollup([r["status"] for r in roadmaps]),
            "roadmaps": roadmaps,
        })

    return projects


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def trunc(s, width):
    return s if len(s) <= width else s[:width - 3] + "..."


def compute_name_width(projects):
    mx = 0
    for proj in projects:
        mx = max(mx, len(proj["name"]))
        for rm in proj["roadmaps"]:
            mx = max(mx, 4 + len(rm["name"]))
            for tk in rm["tracks"]:
                mx = max(mx, 6 + len(tk["slug"]))
                for ms in tk["milestones"]:
                    mx = max(mx, 8 + len(ms["slug"]))
                    for task in ms["tasks"]:
                        mx = max(mx, 10 + len(task["slug"]))
    return min(NAME_WIDTH, mx + 1)


def progress_bar(done, total):
    if total == 0:
        filled = 0
        pct = 0
    else:
        filled = int((done / total) * BAR_WIDTH)
        pct = int((done / total) * 100)
    bar = "[" + "█" * filled + "░" * (BAR_WIDTH - filled) + "]"
    return f"{bar}  {pct:>3}%"


def has_match(item, level, filter_statuses):
    """Return True if item or any descendant has status in filter_statuses."""
    if filter_statuses is None:
        return True
    if item["status"] in filter_statuses:
        return True
    if level == "project":
        return any(has_match(r, "roadmap", filter_statuses) for r in item["roadmaps"])
    if level == "roadmap":
        return any(has_match(t, "track", filter_statuses) for t in item["tracks"])
    if level == "track":
        return any(has_match(m, "milestone", filter_statuses) for m in item["milestones"])
    if level == "milestone":
        return any(t["status"] in filter_statuses for t in item["tasks"])
    return False


def render(projects, filter_statuses=None, hide_types=None, show_all=False):
    if hide_types is None:
        hide_types = {"milestones"}

    if not projects:
        return "  (no projects)"

    W  = compute_name_width(projects)
    BW = BAR_WIDTH + 8
    S  = STATUS_WIDTH
    C  = COUNTS_WIDTH
    SQ = 4

    def row(seq_str, prefix, slug, bar, status, miles, tasks):
        name = trunc(prefix + slug, W)
        return (
            f"{seq_str:>{SQ}} │ {name:<{W}} │ {bar:<{BW}} │ {status:<{S}} │ {miles:>{C}} │ {tasks:>{C}}"
        )

    sep = "─"*SQ + "─┬─" + "─"*W + "─┬─" + "─"*BW + "─┬─" + "─"*S + "─┬─" + "─"*C + "─┬─" + "─"*C
    bot = "─"*SQ + "─┴─" + "─"*W + "─┴─" + "─"*BW + "─┴─" + "─"*S + "─┴─" + "─"*C + "─┴─" + "─"*C

    lines = []
    lines.append(f"{'#':>{SQ}}   {'Name':<{W}}   {'Progress':<{BW}}   {'Status':<{S}}   {'Miles':>{C}}   {'Tasks':>{C}}")
    lines.append(sep)

    def zpad(seq, total):
        w = len(str(total))
        return f"{seq:0{w}d}"

    visible_projects = [p for p in projects if has_match(p, "project", filter_statuses)]

    for pi, proj in enumerate(visible_projects):
        is_lp = (pi == len(visible_projects) - 1)
        lines.append(row(
            zpad(proj["seq"], len(projects)), "", proj["name"],
            progress_bar(proj["tasks_done"], proj["tasks_total"]),
            proj["status"],
            f"{proj['miles_done']}/{proj['miles_total']}",
            f"{proj['tasks_done']}/{proj['tasks_total']}",
        ))
        p_cont = "  " if is_lp else "│ "

        if proj["status"] == "done" and "roadmaps" in hide_types:
            continue

        all_seq_roadmaps = [r for r in proj["roadmaps"] if not r.get("oob")]
        visible_roadmaps = [r for r in proj["roadmaps"]
                            if (not r.get("focus_hidden") or show_all)
                            and has_match(r, "roadmap", filter_statuses)]

        for ri, rm in enumerate(visible_roadmaps):
            is_lr = (ri == len(visible_roadmaps) - 1)
            r_conn = "└ " if is_lr else "├ "
            if rm.get("oob"):
                rm_seq = "·"
            elif rm.get("focus_hidden"):
                rm_seq = "~"
            else:
                rm_seq = zpad(rm["seq"], max(len(all_seq_roadmaps), 1))
            lines.append(row(
                rm_seq, p_cont + r_conn, rm["name"],
                progress_bar(rm["tasks_done"], rm["tasks_total"]),
                rm["status"],
                f"{rm['miles_done']}/{rm['miles_total']}",
                f"{rm['tasks_done']}/{rm['tasks_total']}",
            ))
            r_cont = p_cont + ("  " if is_lr else "│ ")

            if rm["status"] == "done" and "tracks" in hide_types:
                continue

            all_seq_tracks = [t for t in rm["tracks"] if not t.get("oob")]
            visible_tracks = [t for t in rm["tracks"]
                              if (not t.get("focus_hidden") or show_all)
                              and has_match(t, "track", filter_statuses)]

            for ti, tk in enumerate(visible_tracks):
                is_lt = (ti == len(visible_tracks) - 1)
                t_conn = "└ " if is_lt else "├ "
                if tk.get("oob"):
                    tk_seq = "·"
                elif tk.get("focus_hidden"):
                    tk_seq = "~"
                else:
                    tk_seq = zpad(tk["seq"], max(len(all_seq_tracks), 1))
                lines.append(row(
                    tk_seq, r_cont + t_conn, tk["slug"],
                    progress_bar(tk["tasks_done"], tk["tasks_total"]),
                    tk["status"],
                    f"{tk['miles_done']}/{tk['miles_total']}",
                    f"{tk['tasks_done']}/{tk['tasks_total']}",
                ))
                t_cont = r_cont + ("  " if is_lt else "│ ")

                if tk["status"] == "done" and "milestones" in hide_types:
                    continue

                all_seq_milestones = [m for m in tk["milestones"] if not m.get("oob")]
                visible_milestones = [m for m in tk["milestones"]
                                      if (not m.get("focus_hidden") or show_all)
                                      and has_match(m, "milestone", filter_statuses)]
                seq_w = len(str(max(len(all_seq_milestones), 1)))

                for mi, ms in enumerate(visible_milestones):
                    is_lm = (mi == len(visible_milestones) - 1)
                    m_conn = "└ " if is_lm else "├ "
                    if ms["oob"]:
                        seq_str = "·".rjust(seq_w)
                    elif ms.get("focus_hidden"):
                        seq_str = "~".rjust(seq_w)
                    else:
                        ms_seq = next(i + 1 for i, m in enumerate(all_seq_milestones) if m is ms)
                        seq_str = zpad(ms_seq, len(all_seq_milestones))
                    lines.append(row(
                        seq_str, t_cont + m_conn, ms["slug"],
                        progress_bar(ms["tasks_done"], ms["tasks_total"]),
                        ms["status"], "",
                        f"{ms['tasks_done']}/{ms['tasks_total']}",
                    ))

                    if ms["status"] == "done" and "tasks" in hide_types:
                        continue
                    if filter_statuses is None:
                        continue

                    visible_tasks = [t for t in ms["tasks"] if t["status"] in filter_statuses]
                    if not visible_tasks:
                        continue

                    ms_cont = t_cont + ("  " if is_lm else "│ ")
                    for tki, task in enumerate(visible_tasks):
                        is_ltk = (tki == len(visible_tasks) - 1)
                        tk_conn = "└ " if is_ltk else "├ "
                        lines.append(row(
                            zpad(task["seq"], len(ms["tasks"])), ms_cont + tk_conn, task["slug"],
                            "", task["status"], "", "",
                        ))

    lines.append(bot)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        default=None,
        help='Filter rows by status at all levels. "all" shows everything including tasks. Default: all rows shown, no tasks.',
    )
    parser.add_argument(
        "--hide",
        default="milestones",
        help='Suppress children of done parents. Comma-separated: tasks,milestones,tracks,roadmaps. Use "none" to disable. Default: milestones.',
    )
    parser.add_argument(
        "--all", dest="show_all", action="store_true", default=False,
        help="Show focus-hidden items (marked with ~).",
    )
    args = parser.parse_args()

    if args.status is None:
        filter_statuses = None
    elif args.status.strip().lower() == "all":
        filter_statuses = ALL_STATUSES
    else:
        filter_statuses = {s.strip().lower() for s in args.status.split(",")}

    if args.hide.strip().lower() in ("none", ""):
        hide_types = set()
    else:
        hide_types = {s.strip().lower() for s in args.hide.split(",")}

    projects = load_all()
    print()
    print(render(projects, filter_statuses=filter_statuses, hide_types=hide_types, show_all=args.show_all))
    print()


if __name__ == "__main__":
    main()
