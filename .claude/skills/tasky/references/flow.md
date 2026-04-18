# Flow Playbook

The user wants to create, update, remove, or attach a flow. Flows wrap task execution with project-specific steps.

Read `.claude/skills/tasky/references/flow-spec.md` before acting — it defines the full format and execution model.

---

## Create a Flow

Ask:
- What is this flow for? (purpose)
- What steps should run before the task?
- What steps should run after the task?
- Are there standing instructions that apply throughout, or instructions to inject at a specific step?

Write the flow file:
- Skill-owned: `.claude/skills/tasky/references/flows/task-{name}.md`
- Project-owned: `agents/flows/task-{name}.md`

Register it in `nimbility.md` under `## Flows`.

---

## Update a Flow

Read the existing flow file. Make the requested changes. The file is plain markdown — edit directly.

---

## Remove a Flow

Delete the flow file. Remove its entry from the `## Flows` table in `nimbility.md`.

If it was set as the project-wide default (`FLOW: name`), clear that line.

Check if any tasks have `Flow: {name}` set — surface them to the user before removing.

---

## Attach a Flow to a Task

Set the `Flow:` field in the task file to either:
- A registered name (looked up in NIMBILITY.md at execution time)
- A direct path to the flow file

```
Flow: standard
Flow: agents/flows/task-custom.md
```

---

## Set a Project-Wide Default

Edit `nimbility.md` — set the `FLOW:` line to a registered name:

```
FLOW: standard
```

All tasks without a task-level `Flow:` field will use this flow. Leave blank for no default.

---

## Remove a Flow from a Task

Clear the `Flow:` field in the task file:

```
Flow:
```

The task will fall back to the project-wide default, or execute directly if none is set.
