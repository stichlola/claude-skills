---
name: planner-builder
description: Planner-builder (orchestrator-workers + cost-aware model routing) - a strong model (Fable) plans, splits the work and reviews; cheaper models (Opus, Sonnet/Haiku for mechanical steps) write the code and run the checks, each at the effort the sub-task needs. Use when the user says "planner-builder", "fable master + opus builder", "orchestratore", or asks to run a multi-step job as efficiently as possible; also as the default shape for big workflows.
---

# Planner-builder (Fable master + Opus builders)

Known names: **orchestrator-workers** / **planner-executor** (one model plans and supervises,
others execute) combined with **cost-aware model routing** (each sub-task goes to the cheapest
model that does it well). In Claude Code it is a Workflow script whose `agent()` calls set
`model` and `effort` per step.

## When it pays off

- Jobs with several separable pieces (a backlog of fixes, a feature in 3-5 parts, a review).
- Code-heavy work where the hard part is deciding *what* to do (root cause, design), and the
  bulk is writing/building/testing: the planner thinks once, builders do the volume.
- Not worth it for one small fix (one agent, or do it inline) or for pure research.

## Roles and default routing

| Role | Model / effort (default) | Raise when | Lower when |
|---|---|---|---|
| Planner: reads the brief and code map, splits into tasks with acceptance checks, assigns model/effort per task | Fable, medium | unclear root cause, rendering/engine design: high or max | the plan is obvious: skip, plan inline |
| Builder: implements one task in its own worktree, builds, tests, commits | Opus, medium | tricky C++/GOAL/shader, many files: high | mechanical edits, renames, data: low, or Sonnet |
| Checker: runs the test/game, measures, compares shots | Opus low or Sonnet | perf/visual judgement: medium | log/regex checks: Haiku |
| Reviewer: reads the diff + evidence against the acceptance checks, sends back fixes | Fable, medium | release gate, risky merges: high | trivial diffs: skip |

Rule of thumb: start everyone at **medium**; the planner tags each task `easy | normal | hard`
and the script maps it (easy: Opus low / Sonnet, normal: Opus medium, hard: Opus high, and Fable
high only for the one or two tasks where the builder failed twice).

## Shape (Workflow script)

```js
export const meta = { name: 'planner-builder', description: 'Fable plans and reviews, Opus builds',
  phases: [{title:'Plan'},{title:'Build'},{title:'Review'}] }
const ROUTE = { easy: {model:'sonnet', effort:'low'}, normal: {model:'opus', effort:'medium'},
                hard: {model:'opus', effort:'high'} }
phase('Plan')
const plan = await agent(`Plan this job: ${args.goal}. Read the repo map first. Return tasks that
  can run in parallel without touching the same files, each with files, steps, acceptance checks
  and difficulty.`, {model:'fable', effort: args.planEffort || 'medium', schema: PLAN})
const done = await pipeline(plan.tasks,
  t => agent(builderPrompt(t), {...ROUTE[t.difficulty], phase:'Build', isolation:'worktree', schema: BUILT}),
  (b, t) => agent(reviewPrompt(t, b), {model:'fable', effort:'medium', phase:'Review', schema: VERDICT})
    .then(v => v.ok ? b : agent(fixPrompt(t, b, v), {model:'opus', effort:'high', phase:'Build', schema: BUILT})))
return done
```

- Builders get the planner's task text, not the whole conversation: file list, exact acceptance
  checks, project rules (test instances, no push, commit trailer). Keep reports short and fixed.
- One merge step at the end (or per task, by the builder, if the project allows local merges).
- Test slots are the real limit on game projects: tell builders the lock rule (see
  `multi-agent-orchestration`) and cap parallel builders to the free test instances.
- Escalate, don't restart: a failed build/review goes back to a builder one effort step higher,
  with the reviewer's notes; only the second failure goes to Fable.

## How the user calls it

- Shortest: `/squadra <obiettivo>` (a user-level alias skill in `~/.claude/skills/squadra/SKILL.md`
  that points here; create it on a new machine).
- In any session with this plugin: `/studio:planner-builder <goal>` (or just say
  "usa planner-builder per ..."). Optional: "planner high", "builder low" to override.
- The workflow tool needs the user's explicit opt-in: invoking this skill counts as asking for a
  workflow.

## Lessons (Jak Enhanced, 2026-11-11)

- Six agents at once (3 Fable + 3 Opus) hit the 5-hour usage limit together: route volume to
  Opus/Sonnet and keep Fable for plan/review, and resume stopped agents with SendMessage instead
  of starting new ones (their work is saved).
- Memory, not tokens, often decides parallelism: each game test is 3-5 GB commit charge.

## Lessons (Karna split, 2026-11-28)

- A Fable planner at effort high on 3D geometry explored for 30+ min. Give the planner a clear stop rule
  ("concrete plan in <= N steps, no extra renders") and use effort medium for the build.
- To hurry a running planner: SendMessage it "finish now". Its hand-back goes to the main session, NOT
  back into the workflow, so the workflow keeps waiting: stop it, write the plan to a file (PIANO.md),
  launch a build-only workflow that reads it (build opus medium + quick review fable low, max 1 fix).
  Build-only took ~8 min.
- When the job is repetitive geometry, a scripted kit (manifold3d + trimesh, see
  miniature-accessory-rework section 8) beats a team of agents: seconds per cut, no plan phase.
- Interactive Blender add-ons (CatPin and similar draw-on-model splitters) cannot be driven from code;
  check this (bl_idname list, modal tools) before the user buys one for automation.
