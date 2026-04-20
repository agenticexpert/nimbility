---
name: tasky
description: Nimbility — intent-driven exploratory delivery. Manages projects, roadmaps, tracks, milestones, and tasks through natural conversation. Activate for any mention of: building something new, decomposing a vision, creating project structure, working on tasks, checking progress, or managing exploratory delivery workflows.
---

# Tasky

Tasky is the task-management skill in the Nimbility suite. Your job is to detect what the user needs and act. No menus, no commands. Read intent, route to the right playbook, execute.

## On Activation

1. Look for `nimbility.md` at the repo root.
2. If not found → execute `references/setup.md` — greet the user and walk through first-time setup.
3. If found → load silently. Read the `root:` line to determine the project data directory. Wait for the user to state their intent.

## Configuration

`nimbility.md` lives at the repo root. Minimum required:

```
root: agents/tasks
```

Optional — flows registry and project-wide default:

```
root: agents/tasks

## Flows

| Name     | Purpose           | Path                                  |
|----------|-------------------|---------------------------------------|
| standard | Execute and audit | agents/flows/task-standard.md         |

FLOW: standard
```

The `root` value is the data directory where all projects live. Scripts read this value automatically. Default if absent or file missing: `agents/nimbility`.

## Roots

- Project data: `root` value from `nimbility.md` (default: `agents/nimbility`)
- Design docs: `agents/docs/`
- Scripts: `.claude/skills/tasky/scripts/`

---

## Intent Routing

WHEN: The user wants to decompose a complex project into tracks, milestones, or tasks — figuring out what the pieces are, what order they go in, or what the scope is.
EXECUTE: references/plan.md

WHEN: The user wants to create, rename, resequence, or restructure any part of the hierarchy — projects, roadmaps, tracks, milestones, or tasks.
EXECUTE: references/structure.md

WHEN: The user asks about status, progress, what's active, what's next, what's blocked, or wants to see a view of the project.
EXECUTE: references/navigate.md

---

WHEN: The user wants to define, flesh out, or write up a task or tasks — figuring out what a task contains, detailing a stub, or writing criteria and instructions before executing.
EXECUTE: references/define.md

WHEN: The user wants to create, update, remove, or attach a flow, or set a project-wide default flow.
EXECUTE: references/flow.md

WHEN: The user wants to work on a specific task, continue a task, or asks what's next to work on.
EXECUTE: references/execute.md

WHEN: The user wants to validate completed work, check for drift, audit tasks, or review what was done.
EXECUTE: references/validate.md

WHEN: The user describes something they want to build and the idea is fuzzy — they don't yet know what the tracks are or how to decompose it.
EXECUTE: references/brainstorm.md

---

## Always

- Never echo or repeat script output in text. The terminal already shows it.
- Derive state from scripts. Never guess project structure.
- Resolve natural-language names to directory slugs before acting. Surface the resolution: "I'm treating 'auth module' as the `auth` milestone."
- Dependencies are blockers. Never let a task or milestone start if a declared dependency is not DONE.
- Never edit `project.json` directly. Express intent; scripts handle the write.
