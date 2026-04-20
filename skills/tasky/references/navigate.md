# Navigate Playbook

The user wants to know where things stand. Answer with data from scripts. Never guess state from memory or context — always run the appropriate script.

---

## On Every Navigate Request

Run `view_all.py` as the default view. No `--status` flag shows all rows without task expansion; add `--status` to filter and expand tasks.

```
python .claude/skills/tasky/scripts/view_all.py
```

To see active work with tasks expanded:
```
python .claude/skills/tasky/scripts/view_all.py --status doing,paused,ready,pending
```

Use `scan.py` only when you need the raw data structure (e.g. to resolve slugs, check dependencies, or feed another script).

---

## Common Questions → Scripts

### Show the full hierarchy

```
python .claude/skills/tasky/scripts/view_all.py [--status <statuses>]
```

Full tree: every project → roadmap → track → milestone. Flags:
- `--status <list>` — filter rows at all levels to matching status only; also expands tasks for matching milestones. Use `all` to show everything including tasks.
- `--hide <types>` — suppress children of done parents. Values: `tasks,milestones,tracks,roadmaps`. Default: `milestones`.
- `--all` — show focus-hidden roadmaps, tracks, and milestones (marked `~`).

### What's the overall status?

```
python .claude/skills/tasky/scripts/view_projects.py [<project>]
```

Shows each roadmap with rollup status and Tracks / Miles / Tasks counts. Omit project to see all projects. Add `--all` to show focus-hidden roadmaps.

### What's the status of a roadmap?

```
python .claude/skills/tasky/scripts/view_tracks.py <project> <roadmap>
```

Shows each track with rollup status and progress count. Add `--all` to show focus-hidden tracks.

### What's hidden / what's in focus?

```
python .claude/skills/tasky/scripts/view_all.py --all
python .claude/skills/tasky/scripts/view_projects.py --all
python .claude/skills/tasky/scripts/view_tracks.py <project> <roadmap> --all
python .claude/skills/tasky/scripts/view_milestones.py <project> <roadmap> --all
```

`--all` reveals focus-hidden items marked `~`. Totals always include hidden items regardless — `--all` only affects what rows are shown. To see the full hide list, read `project.json["focus"]["hide"]`.

### What's active right now?

```
python .claude/skills/tasky/scripts/scan.py --status DOING
```

Lists everything currently DOING across all projects. If nothing is DOING, show PENDING next.

### What's next?

```
python .claude/skills/tasky/scripts/view_all.py --status pending,ready,doing
```

Shows the active picture — what's in progress, what's ready to start, and what's pending. This respects the full visual hierarchy including track-level dependencies.

### What's blocked?

```
python .claude/skills/tasky/scripts/scan.py --blocked
```

Lists tasks/milestones that have unmet dependencies, with the blocking dependency named.

### Show the dependency graph

Track deps in a roadmap:
```
python .claude/skills/tasky/scripts/view_deps.py <project> <roadmap>
```

Milestone deps in a track:
```
python .claude/skills/tasky/scripts/view_deps.py <project> <roadmap> <track>
```

Task deps in a milestone:
```
python .claude/skills/tasky/scripts/view_deps.py <project> <roadmap> <track> <milestone>
```

Terminal ASCII tree. Each node owns its branch; children hang below their parent. Shows status char, seq, and slug.

### Show me the tasks in a track/milestone

```
python .claude/skills/tasky/scripts/view_tasks.py <project> <roadmap> <track> [<milestone>]
```

Lists tasks with status, criteria completion percentage, and dependency state.

### Show me the milestone Gantt

```
python .claude/skills/tasky/scripts/view_milestones.py <project> <roadmap>
```

Terminal Gantt. Milestones as rows, slot columns left to right. Concurrent milestones share a slot. Progress bar anchored to slot columns.

---

## Interpreting Results

Present results plainly. Don't over-narrate. If the user asks "what's next?" give them the next task and its milestone/track context — one thing, not a list of options.

If there's nothing DOING and nothing unblocked, surface that directly:
> "Everything is blocked. The next unblocked item is `{slug}` in `{track}` — but it's waiting on `{dep}`."

If the project is empty or has no tasks yet, say so and offer to help set up structure.

---

## Scoping

If multiple projects exist and the user doesn't specify, ask which project before running. If only one project exists, assume it.
