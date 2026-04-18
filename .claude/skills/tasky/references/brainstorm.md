# Brainstorm Playbook

The user has an idea but no project structure yet. Your job is to ask the right questions, surface what they haven't thought of, and get to the point where the tracks are nameable. Then hand off to structure.

---

## What You're Doing

Not decomposing. Not planning. Exploring.

The user knows what they want to build but not what it consists of. Brainstorm is the gap between impulse and structure. You're helping them find the shape of the thing before committing it to a hierarchy.

**Exit condition — two sentences:**

> **{project}** has **{n}** roadmap(s): **{roadmap-slugs}**. The first one to build is **{roadmap}**.
>
> **{roadmap}** has these tracks: **{track-slugs}**.

When the user can confirm both sentences, brainstorm is done. Everything before that is exploration. Everything after that is structure and plan.

---

## How to Run It

Ask questions in rounds. Don't fire all of them at once — read what the user gives you and probe what's still unclear.

**Round 1 — What is it?**
Get a crisp picture of the thing. Ambiguous answers mean more questions.
- What does it do? Who uses it?
- What does "done" look like for version 1?
- Is this a standalone thing or part of something larger?
- What's the output — a file, a rendered experience, a deployed service?

**Round 2 — What are the hard parts?**
Surface the concerns the user may not have named yet.
- What do you know you don't know?
- What's the riskiest assumption in this?
- Are there domain constraints (hardware limits, format specs, platform rules) that shape everything else?
- What have you tried before that didn't work, or seen fail elsewhere?

**Round 3 — Where are the seams?**
Find where the thing naturally splits.
- What could be built independently by different people?
- What has to be done before anything else can be done?
- What's UI vs. logic vs. data vs. pipeline?
- Are there external systems this depends on?

---

## Proposing the Shape

When you have enough to work with, fill in the two sentences and present them:

> **{project}** has **{n}** roadmap(s): **{roadmap-slugs}**. The first one to build is **{roadmap}**.
>
> **{roadmap}** has these tracks: **{track-slugs}**.

A roadmap is a major version, platform, or phase — something with its own delivery arc. "v1" and "v2" are roadmaps. "mobile" and "web" are roadmaps.

A track is a major concern within a roadmap — something that can be built largely independently. "backend", "frontend", "data-pipeline" are tracks.

Keep roadmaps to 2–5. Keep tracks to 4–8 per roadmap. If either list is longer, something is too granular.

Ask: "Does this feel right? Anything missing or wrongly scoped?"

Iterate on both sentences until the user confirms.

---

## Handing Off

Once both sentences are confirmed, hand off:

1. Execute structure.md — create the project, roadmaps, and tracks for the first roadmap
2. The user is now ready to plan — execute plan.md to decompose the first roadmap's tracks into milestones and tasks

Don't create anything until the user confirms both sentences. Brainstorm is conversation — structure is commitment.
