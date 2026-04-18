# Execute Playbook

The user wants to work a task. Identify which task, load it, do the work, update it.

---

## Identifying the Task

**User names a specific task** — resolve it (alias if needed) and load it.

**User says "continue" or "resume"** — if there is a DOING task in the known milestone context, that is the task. If the milestone isn't known, ask.

**User says "next"** — two cases:
- A DOING task exists in the milestone → disambiguate: "Do you mean resume `{doing-task}` or start `{next-task}`?"
- No DOING task exists → first task in sequence with status `pending` or `paused`. If the next task is `todo` (undefined stub), offer to define it first before executing.

If the milestone context isn't known in either case, ask: "Which milestone?"

**Anything else ambiguous** — ask. Don't infer.

---

## Before Starting

Verify all declared dependencies are DONE. If any are not:
- Name the blocker.
- Stop. Do not proceed.

---

## Loading a Task

Read the task file. Fields:

- **Description** — 1-2 sentence overview of what this task is
- **Goal** — what this task produces or achieves
- **Criteria** — checkboxes. Always the acceptance gate. May also be the instruction (see below).
- **References** — paths to specs, design docs, or other material. Load each into context before working.
- **Task** — the instruction. If populated, this is what to do. Written in impact/execution form.

**If `## Task` is populated:** work from Task. Criteria is the acceptance gate — check each item off when verified.

**If `## Task` is empty:** Criteria is both the instruction and the acceptance gate. Work each item, check it off when done.

If both Task and Criteria are empty (placeholder task), ask the user if they want to flesh it out first, or give you verbal instructions to work from.

---

## Starting Work

Set status to DOING:
```
python manage_tasks.py set-status <project> <roadmap> <track> <milestone> <slug> doing
```

Load every path listed in `## References` into context before starting. Don't work from memory when a reference exists.

**Resolve the flow:**

1. Check the task file's `Flow:` field
   - If it's a registered name → look up the path in `nimbility.md` Flows table
   - If it's a path → use it directly
2. If the task has no `Flow:` → check `nimbility.md` for a project-wide `FLOW:` default
3. If no flow resolves → execute the task directly

If a flow resolves, read the flow file and execute through its steps in order. `{task}` is where the task's criteria or Task instruction executes. See `.claude/skills/tasky/references/flow-spec.md` for full execution rules.

---

## Working

Work through the task (or flow sequence if declared). When each criterion is satisfied, check it off:
- `[ ]` → `[x]`

If something unexpected surfaces — wrong assumption, missing piece, design conflict — tell the user before continuing. Don't paper over it.

---

## Pausing

If work must stop before completion:
```
python manage_tasks.py set-status <project> <roadmap> <track> <milestone> <slug> paused
```

Checked criteria preserve what was done. When work resumes, pick up from the first unchecked criterion (or the flow step containing it).

---

## Completing

All criteria checked → set status to READY, not DONE. READY means the work is done but has not been validated yet. The user must confirm before DONE is set.

```
python manage_tasks.py set-status <project> <roadmap> <track> <milestone> <slug> ready
```

Tell the user the task is ready for validation. Wait. Do not mark DONE until they confirm.

Once the user confirms:

```
python manage_tasks.py set-status <project> <roadmap> <track> <milestone> <slug> done
```

---

## Writing a Task

When filling in a task before working it:

- **Description**: what this task is. 1-2 sentences.
- **Goal**: the outcome. One clear sentence. "Produces X" or "Enables Y."
- **Criteria**: write tight, verifiable items. Vague criteria are vague acceptance tests. "Passes test X" beats "works correctly." Aim for 5–15 items. More → consider decomposing the task.
- **References**: only list what will actually be read.
- **Task**: impact/execution form. What to do and what it achieves. Not background. If left empty, criteria carries the load.

Empty tasks are valid placeholders. Fill them in when you're about to work them — that's when you have enough context to write them correctly.
