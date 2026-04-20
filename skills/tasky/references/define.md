# Define Playbook

The user wants to define one or more tasks — figuring out what they contain, writing them up, or fleshing out stubs. This is not executing. It's making tasks workable.

---

## Status Lifecycle

```
todo → pending → doing → paused (back to doing)
                       → ready → done
```

| Status | Meaning |
|---|---|
| `todo` | Stub — exists in the sequence but not yet defined (empty or near-empty) |
| `pending` | Defined and ready to execute — waiting to be picked up |
| `doing` | Actively being worked |
| `paused` | Started but on hold — criteria preserve partial progress |
| `ready` | Work complete, awaiting user validation |
| `done` | Validated and closed |
| `x` | No status — not applicable |

**Define moves a task from `todo` → `pending`.** A task should not be executed until it is at least `pending`.

---

## What You're Doing

Turning a milestone or stub into tasks that are ready to execute. The goal is not a complete plan — it's enough definition to be actionable.

Tasks don't all need the same level of detail. Define each task at the level it needs to be executable. No more.

---

## Starting Point

Three entry points:

**Milestone with no tasks** — surface what the tasks are, stub them in sequence.

**Stub tasks that need fleshing out** — identify which ones, ask what's needed, fill them in.

**A specific task to define** — focus on that one task, ask the minimum to make it workable.

Load the milestone's tasks with:
```
python .claude/skills/tasky/scripts/manage_tasks.py list <project> <roadmap> <track> <milestone>
```

---

## Surfacing Tasks for a Milestone

If no tasks exist yet, ask:

- What does this milestone deliver? What's true when it's done that wasn't true before?
- What's the first thing that has to happen?
- What are the discrete pieces — things that could be reviewed or verified independently?
- What can't start until something else finishes?

From the answers, propose a task sequence. Name them, order them, surface dependencies. Don't detail yet — get them on the board first.

Create stubs:
```
python .claude/skills/tasky/scripts/manage_tasks.py create <project> <roadmap> <track> <milestone> <slug>
```

Confirm the sequence with the user before moving to detail.

---

## Detail Levels

**Stub** — name only. Exists so it isn't forgotten. Valid to execute from if context is obvious.

**Loose** — Description filled in. One or two sentences. Enough that someone coming cold understands what it is.

**Workable** — Description + either Criteria or Task populated. Enough to execute without asking questions mid-task.

**Detailed** — Full task: Description, Goal, Criteria, References, Task instruction. Used when the work is complex, has precise acceptance requirements, or the interface needs to be exactly right.

The task being worked next should be at least Workable. Everything else can stay Stub or Loose.

---

## Defining a Single Task

Ask only what's needed to reach the target detail level:

**To make it Workable:**
- What does this task produce or change?
- How will you know it's done? (surfaces Criteria)
- Is there anything it should explicitly not do?

**To make it Detailed:**
- What's the instruction? What exactly should be built? (surfaces Task section)
- Are there references — specs, designs, prior tasks — that inform this?
- What does it depend on?

Write the answers into the task file. Don't ask for information you can infer from context.

---

## Writing the Task File

Fill in only what's needed. Leave sections blank if they add no value.

- **Description** — what this task is. 1-2 sentences.
- **Goal** — what it produces. One clear sentence.
- **Criteria** — verifiable items. If Task is empty, Criteria is both the instruction and the gate. Write tight, checkable items.
- **References** — only paths that will actually be read during execution.
- **Task** — the instruction in impact/execution form. What to do and what it achieves. If populated, Criteria becomes the acceptance gate only.

---

## Exit

When the task or tasks are defined at the right detail level for what's coming next, set status to `pending`:

```
python .claude/skills/tasky/scripts/manage_tasks.py set-status <project> <roadmap> <track> <milestone> <slug> pending
```

The user can execute immediately or come back later. If executing now, hand off to execute.md.
