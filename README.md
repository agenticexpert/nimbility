# Nimbility

Nimbility currently ships **Tasky** — a lightweight skill for turning a deliverable into a practical execution plan without heavy process overhead.

## What Tasky does

Tasky helps you:
- break down a fuzzy idea into roadmaps, tracks, milestones, and tasks
- identify what’s next and what’s blocked
- execute and validate progress through natural conversation

## How it feels to use

Example prompts:

- “Let’s plan out the roadmap for <topic>”
- “Start milestone <x>”
- “Start task <x>”
- “Let’s prepare task <x> for execution”
- “Let’s audit [roadmap|track|milestone|task] for readiness to execute”
- “What’s next?”
- “View [all|project|roadmap|tracks|milestones|tasks]”

## Installation

```bash
# All skills
npx skills add agenticexpert/nimbility

# Tasky only
npx skills add agenticexpert/nimbility/.claude/skills/tasky
```

## Updates

```bash
# By repo source
npx skills update agenticexpert/nimbility

# By skill name
npx skills update tasky
```

## Learn more

For full setup, behavior, and workflows, see:

- [Tasky README](.claude/skills/tasky/README.md)
