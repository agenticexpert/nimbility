# Tasky

Tasky is a Claude Code skill for **intent-driven exploratory delivery**.  
It is built for vibe coders and exploratory creators who want to stay in creative flow while adding just enough structure to ship. It is also for anyone with a deliverable who wants to break work into clear steps and execute confidently. Tasky intentionally avoids enterprise-heavy process overhead and focuses on lightweight, practical execution through natural conversation.

## Who Tasky Is For

Tasky is for:
- Vibe coders who want to keep creative momentum and avoid heavy process
- Builders with a concrete deliverable who want to break it into executable steps
- Solo makers or small teams that want lightweight structure without enterprise ceremony
- Exploratory product and prototype work where clarity is needed but rigidity is not

Tasky is probably not for:
- Organizations requiring strict enterprise governance workflows and approval gates
- Teams that prefer heavyweight PM tooling and strict process enforcement
- Environments where every step must be formalized before exploration begins

Tasky manages work as a file-based hierarchy:

```
project → roadmap → track → milestone → task
```

- **Project**: top-level product or initiative
- **Roadmap**: major phase/version
- **Track**: workstream within a roadmap (e.g., backend, frontend, infra)
- **Milestone**: scoped deliverable in a track
- **Task**: executable unit of work with criteria

---

## What Tasky Does

Tasky routes your request to the right workflow automatically:

- Planning and decomposition (when ideas are still fuzzy)
- Creating and restructuring projects/roadmaps/tracks/milestones/tasks
- Showing status, next work, and blockers
- Defining task specs before execution
- Executing and validating completed work
- Managing reusable flows for execution standards

Tasky state is stored in plain files:
- `nimbility.md` controls global config (repo root)
- project data lives under `root:` from `nimbility.md`
- ordering/dependencies live in each project's `project.json`
- task content is markdown files in the hierarchy

---

## Prerequisites

- **Python 3.7+** (standard library only; no pip dependencies)
- **Claude Code** with skills support
- **OS**: macOS, Linux, Windows

---

## Installation

1. Copy this directory into your repo:
   - `.claude/skills/tasky/`
2. Register the skill in `.claude/settings.json`:
   ```json
   {
     "skills": [".claude/skills/tasky/SKILL.md"]
   }
   ```
3. Add `nimbility.md` at repo root:
   ```yaml
   root: agents/tasks
   ```

If `nimbility.md` is missing, Tasky can guide setup on first activation.

---

## Quickstart (How to Use Tasky)

You use Tasky by stating intent in normal language.

### Example prompts

- “I want to build a payments feature. Help me break it down.”
- “Create a roadmap for v1 and tracks for backend/frontend.”
- “What’s next to work on?”
- “Show me what’s blocked.”
- “Start the auth milestone.”
- “Validate what was completed in this task.”

### Typical flow

1. Describe what you’re building.
2. Let Tasky create/organize structure.
3. Ask for next unblocked work.
4. Execute tasks.
5. Validate and review completion.

---

## Intent Routing

Tasky’s behavior is defined in `SKILL.md`, which maps user intent to playbooks in `references/`:

- `plan.md` — decomposition and planning
- `structure.md` — create/rename/resequence hierarchy
- `navigate.md` — status and views
- `define.md` — flesh out task details
- `execute.md` — work execution flow
- `validate.md` — audit and drift checks
- `brainstorm.md` — fuzzy idea shaping
- `flow.md` — flow management

---

## Views and Utility Scripts

You can inspect state directly via scripts:

```bash
python .claude/skills/tasky/scripts/view_all.py
python .claude/skills/tasky/scripts/view_all.py --status doing,pending
python .claude/skills/tasky/scripts/view_all.py --all
python .claude/skills/tasky/scripts/view_projects.py
python .claude/skills/tasky/scripts/view_tracks.py <project> <roadmap>
python .claude/skills/tasky/scripts/view_milestones.py <project> <roadmap>
python .claude/skills/tasky/scripts/view_deps.py <project> <roadmap> [<track>] [<milestone>]
```

---

## Safety Rules

Tasky enforces constraints to keep project data safe and consistent:

- **Strict slug format** for identifiers:
  - `^[a-z0-9-]+$`
  - applies to project/roadmap/track/milestone/task slugs and dependency slugs
- **Dependency gating**:
  - items with unmet dependencies are treated as blocked
- **Path safety**:
  - path-like inputs are validated to prevent traversal/injection
- **project.json handling**:
  - workflows/scripts own structured writes; avoid hand-editing during normal operation

---

## Portability Notes (macOS / Linux / Windows)

Tasky scripts are cross-platform Python and use `os.path`-based path handling.

Config/root discovery is **cwd-independent**:
- scripts locate repo config by walking upward for `nimbility.md` / `.git`
- scripts can run from non-root working directories and still resolve `root` correctly

---

## Troubleshooting

### Skill does not activate
- Confirm `.claude/settings.json` includes:
  - `.claude/skills/tasky/SKILL.md`
- Restart Claude Code session after updating settings.

### “Config not found” or unexpected root
- Ensure `nimbility.md` exists at repo root with:
  ```yaml
  root: agents/tasks
  ```
- Run:
  ```bash
  python .claude/skills/tasky/scripts/view_all.py
  ```

### Slug rejected
- Use lowercase letters, numbers, and hyphens only.
- Example valid slug: `auth-session-hardening`

---

## License

Tasky is licensed under Apache 2.0. See `LICENSE`.

---

## Part of Nimbility

Tasky is one skill in the Nimbility suite, focused on exploratory delivery and execution orchestration.
