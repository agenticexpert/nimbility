# Structure Playbook

The user wants to create, rename, resequence, or restructure the hierarchy. Execute precisely. Confirm before writing. Show what you're about to create and get a yes before running scripts.

---

## Hierarchy Rules

```
{root}/
  {project}/                  ← no prefix
    project.json              ← ALL ordering and deps metadata, script-managed only
    {roadmap}/                ← no prefix
      {track}/                ← no prefix
        {milestone}/          ← no prefix, e.g. backend-api/
          {task}.md           ← no prefix, e.g. application-model.md
```

- **No `nn-` prefixes anywhere.** Filenames are plain slugs at every level.
- **All ordering lives in `project.json`** — roadmaps, tracks, milestones, and tasks each have an ordered array.
- The slug is the stable identity for dependency references.
- No files at project, roadmap, track, or milestone level. Directory existence is the record.

### project.json schema

```json
{
  "roadmaps": ["v1", "v2"],
  "tracks": {
    "v1": {
      "order": ["scaffolding", "core", "api", "polish"],
      "deps": {
        "core": ["scaffolding"],
        "api": ["core"],
        "polish": ["api"]
      }
    }
  },
  "milestones": {
    "v1/scaffolding": ["project-setup"],
    "v1/api": ["endpoints"]
  },
  "tasks": {
    "v1/scaffolding/project-setup": [
      "repo-init", "ci-setup", "base-layout", "env-config"
    ]
  },
  "focus": {
    "hide": {
      "roadmaps": ["v2"],
      "tracks": { "v1": ["polish"] },
      "milestones": { "v1/api": ["endpoints"] }
    }
  }
}
```

The `#` (seq) shown in views is derived at render time from position in these arrays — never stored.

`focus.hide` is optional. All items are in-focus by default. Items in the hide lists are suppressed from views unless `--all` is passed. Totals always reflect the full project regardless.

---

## Alias Resolution

Users will use natural names that may not match directory slugs. Before calling any script, resolve the name:

1. Run `scan.py` to get the current project graph.
2. Match the user's term against existing slugs (fuzzy match).
3. If ambiguous, ask: "Did you mean X or Y?"
4. Never guess silently. Surface the resolution: "I'm treating 'auth module' as the `auth` milestone."

---

## Creating Structure

### Confirm Before Writing

Show the user what you're about to create before running any script:

```
I'll create:
  {root}/my-project/
  {root}/my-project/project.json
  {root}/my-project/v1/
  {root}/my-project/v1/core/
```

Get confirmation, then run.

### Project

```
python .claude/skills/tasky/scripts/manage_projects.py create-project <slug>
```

Creates `{root}/{slug}/` and an empty `project.json`.

### Roadmap

```
python .claude/skills/tasky/scripts/manage_roadmaps.py create <project> <slug>
```

Creates `{root}/{project}/{slug}/` and appends to `project.json["roadmaps"]`.

### Track

```
python .claude/skills/tasky/scripts/manage_tracks.py create <project> <roadmap> <slug>
```

Creates `{root}/{project}/{roadmap}/{slug}/` and appends to `project.json["tracks"][roadmap]["order"]`.

### Milestone

```
python .claude/skills/tasky/scripts/manage_milestones.py create <project> <roadmap> <track> <slug> [--insert <n>] [--deps <slug,...>]
```

- `--insert <n>` — places at position n in the order array (1-based), shifting others down.
- No flag — appends to end.

Creates the directory and registers in `project.json["milestones"]`.

### Task

```
python .claude/skills/tasky/scripts/manage_tasks.py create <project> <roadmap> <track> <milestone> <slug> [--insert <n>] [--deps <slug,...>]
```

- `--insert <n>` — places at position n in the order array (1-based).
- No flag — appends to end.

Creates `{slug}.md` with the standard template and registers in `project.json["tasks"]`.

---

## Status Lifecycle

| Status | Meaning |
|---|---|
| `todo` | Stub — exists in sequence, not yet defined |
| `pending` | Defined, ready to execute — waiting to be picked up |
| `doing` | Actively being worked |
| `paused` | Started but on hold |
| `ready` | Work complete, awaiting user validation |
| `done` | Validated and closed |
| `x` | No status / not applicable |

Flow: `todo` → (define) → `pending` → (start) → `doing` → (finish) → `ready` → (validate) → `done`

New tasks are created with `Status: TODO`. The define step moves them to `PENDING`.

---

## Task Template

```markdown
# {Title}

Status: TODO
Dependencies: [{dep-slug}, ...]
Flow:

## Description


## Goal


## Criteria


## References


## Task

```

Leave Dependencies empty if none. Purpose, Criteria, and Details start empty — they fill in during execution.

---

## Resequencing (same parent)

```
python .claude/skills/tasky/scripts/manage_milestones.py move <project> <roadmap> <track> <slug> --insert <n>
python .claude/skills/tasky/scripts/manage_tasks.py move <project> <roadmap> <track> <milestone> <slug> --insert <n>
```

Reorders within the parent's array in project.json. No filesystem changes. Scripts validate that no resequence places a dependency after the dependent.

---

## Moving to a Different Parent (cross-parent)

Any item can be moved to another valid container of the same type:

| Item | Moves to | `--dest` format |
|---|---|---|
| task | different milestone | `roadmap/track/milestone` |
| milestone | different track | `roadmap/track` |
| track | different roadmap | `roadmap` |
| roadmap | different project | `project` |

```
python .claude/skills/tasky/scripts/manage_tasks.py move <...path...> <slug> --dest <roadmap/track/milestone> [--insert <n>]
python .claude/skills/tasky/scripts/manage_milestones.py move <...path...> <slug> --dest <roadmap/track> [--insert <n>]
python .claude/skills/tasky/scripts/manage_tracks.py move <project> <roadmap> <slug> --dest <roadmap> [--insert <n>]
python .claude/skills/tasky/scripts/manage_roadmaps.py move <project> <roadmap> --dest <project> [--insert <n>]
```

**Dep validation blocks the move** if any sibling dependency would be broken:
- Outbound: deps the moving item holds on old siblings
- Inbound: old siblings that depend on the moving item

If conflicts exist, the script errors with the list of affected deps. Resolve them first with `remove-dep`, then retry the move.

---

## Adding Dependencies

```
python .claude/skills/tasky/scripts/manage_tasks.py add-dep <...path...> <slug> <dep-slug>
python .claude/skills/tasky/scripts/manage_milestones.py add-dep <...path...> <slug> <dep-slug>
python .claude/skills/tasky/scripts/manage_tracks.py add-dep <project> <roadmap> <track> <dep-track>
```

Dependencies are always scoped to siblings. Validate before writing.

---

## Track Ordering and Dependencies

```
python .claude/skills/tasky/scripts/manage_tracks.py add-dep <project> <roadmap> <track> <dep-track>
```

This writes to `project.json["tracks"][roadmap]["deps"]`. Never edit `project.json` directly.

The view scripts topologically sort tracks by their deps — so the track that must go first appears first.

---

## Setting Focus (Hide / Unhide)

Focus controls which roadmaps, tracks, and milestones are visible in views by default. Everything is in-focus unless explicitly hidden.

### Hide

```
python .claude/skills/tasky/scripts/manage_roadmaps.py hide <project> <roadmap>
python .claude/skills/tasky/scripts/manage_tracks.py hide <project> <roadmap> <track>
python .claude/skills/tasky/scripts/manage_milestones.py hide <project> <roadmap> <track> <milestone>
```

### Unhide

```
python .claude/skills/tasky/scripts/manage_roadmaps.py unhide <project> <roadmap>
python .claude/skills/tasky/scripts/manage_tracks.py unhide <project> <roadmap> <track>
python .claude/skills/tasky/scripts/manage_milestones.py unhide <project> <roadmap> <track> <milestone>
```

**Rules:**
- OOB items cannot be hidden (they're already separate).
- Hidden items are excluded from all view rows by default.
- Totals (progress bars, task counts) always include hidden items — true state is never obscured.
- `--all` on any view script reveals hidden items marked with `~`.

---

## Batch Creation

When creating a full structure from a plan session, build top-down and confirm the whole batch at once before running:

1. Show the complete proposed structure.
2. Get one confirmation.
3. Run scripts strictly in this order — each level must exist before the next is created:

```
1. project       manage_projects.py create-project
2. roadmap       manage_roadmaps.py create
3. track(s)      manage_tracks.py create          (all tracks for this roadmap)
4. milestone(s)  manage_milestones.py create       (all milestones per track)
5. task(s)       manage_tasks.py create            (all tasks per milestone)
```

Never create a child before its parent exists.
