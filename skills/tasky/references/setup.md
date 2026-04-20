# Setup Playbook

No `nimbility.md` was found at the repo root. This is a first-time setup. Greet the user and walk through configuration.

---

## Greeting

Say something like:

> Welcome to Tasky. I don't see a `nimbility.md` config file yet. Let me help you set one up — it only takes a moment.

---

## Step 1 — Choose a Root Directory

Ask:
> Where do you want to store your project data? This is the directory where all your projects, roadmaps, milestones, and tasks will live.
>
> Common choices:
> - `agents/tasks` — if you want tasks alongside your code
> - `tasks` — at repo root
> - `.tasks` — hidden directory

Wait for the user to decide. Suggest a default if they're unsure: `agents/tasks`.

---

## Step 2 — Write nimbility.md

Create `nimbility.md` at the repo root:

```markdown
root: {chosen-path}
```

Tell the user the file was created and what it does.

---

## Step 3 — Create the Root Directory

Run:
```
mkdir -p {chosen-path}
```

---

## Step 4 — Offer to Create the First Project

Ask:
> What's the first project you want to work on? I can create the structure now, or you can do that when you're ready.

If they give a name → hand off to `structure.md` to create the project.
If they want to wait → tell them they're set up and can start any time.

---

## Notes

- `nimbility.md` can also hold a flows registry and project-wide default flow. See `flow.md` for details.
- The root directory can be anything — it doesn't need to be inside `agents/`.
- Running any script without `nimbility.md` will use the default root: `agents/nimbility`.
