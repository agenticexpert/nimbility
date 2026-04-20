# Validate Playbook

The user wants to review completed work for drift. Run the mechanical checks, then do the judgment-based review.

---

## READY Tasks

READY tasks are the primary validation target. They are complete but awaiting human sign-off before DONE. Surface all READY tasks first:

```
python .claude/skills/tasky/scripts/scan.py --status READY
```

For each READY task: read it, confirm criteria are all checked and the work looks real. If it passes, mark DONE. If not, flag the issue to the user and set back to DOING.

---

## Step 1 — Mechanical Checks

Run validate.py to surface structural drift:

```
python .claude/skills/tasky/scripts/validate.py
```

Or scoped to a project:

```
python .claude/skills/tasky/scripts/validate.py --project <slug>
```

The script checks:
- **DONE with unchecked criteria** — task is marked done but criteria weren't all verified
- **DONE with empty Criteria** — nothing verifiable was recorded; can't confirm the work was real
- **Bypassed dependency** — task is DONE but a declared dependency is not
- **Broken reference path** — a `## References` entry points to a file that doesn't exist

If issues are found, surface them to the user before continuing. Each issue is a structural problem — something the system can see without reading the work.

---

## Step 2 — Audit

For each DONE task in scope, read the task file and verify:

- Criteria items are specific and clearly checked off — not vague, rubber-stamped, or left empty
- The `## Task` section (if populated) reflects what was actually done, not what was planned
- References that were loaded during the task still exist and weren't silently renamed or deleted

This is a judgment call. The machine can't make it. Look for tasks that look too easy — done too fast, criteria too vague, details section empty.

---

## Step 3 — Drift Detection

Two kinds:

### Divergence Drift
Unintentional. Something is out of sync with the spec or design.

For each completed task:
1. Load its `## References` files
2. Compare the task's criteria and outcomes against the expectations in those documents
3. Flag where reality no longer matches the reference

Divergence = something went wrong or took a different path than the spec described. Surface it to the user.

### Evolution Drift
Intentional. The work moved in a better direction and the implementation is correct — but the reference docs still describe the old approach.

For each completed task where the work visibly differs from the references:
1. Identify which reference docs are now stale
2. Note what changed and why (if inferable from the task)
3. Present the stale docs to the user — they need to be updated so future tasks working from those docs aren't misled

Evolution drift is not a bug. It's a knowledge maintenance signal. The task was right; the docs need to catch up.

---

## Reporting

Present issues in two passes:

**Mechanical (validate.py output):** List verbatim — these are definitive.

**Judgment (audit + drift):** Summarize what was found. For each drift signal, name:
- The task where it was found
- The reference doc that's affected
- Whether it looks like divergence (something went wrong) or evolution (docs need updating)

Let the user decide how to act on each. Don't assume — surface and wait.
