---
name: multi-agent-orchestration
description: How to run sub-agents and dynamic workflows cheaply and safely on a big game project - token economy rules, the research/implement/verify/fix workflow shape, resuming a workflow without redoing finished agents, stopping agents without leaving debug edits behind, and slow-line release uploads. Use before spawning agents or writing a Workflow script, and when the user asks to save tokens.
---

# Orchestrating agents and workflows

Lessons from long sessions on Jak Enhanced (OpenGOAL fork: C++, GOAL, shaders, Blender, releases).

## Keeping these skills alive (user rule)

- Every session and every sub-agent/workflow agent reads **all the general skills** (this one and
  `cloud-agent-workflow`) before working, and skims the topic skills' descriptions in the README.
- When you learn something reusable, or notice a missing lesson, add it to the right skill (or a new
  one; a skill for every project also goes in the README's "general skills" table), then **commit and
  push `stichlola/claude-skills` right away, without asking** — an unpushed skill is invisible to other
  projects and chats.
- In a workflow script, tell agents to read the general skills in the shared prompt context.

## Token economy (user rule)

Most tokens go to agents reading big files and logs, screenshots and retries — not to prose. So:

1. **Lower effort for mechanical work**: research, simple checks, uploads → `effort: 'low'`/`'medium'`;
   keep the default only for the implementer and hard verify/judge stages.
2. **Few screenshots**, only ones that prove something; downscaled (zoom a region, ~960 px wide);
   at most ~4 per game run.
3. **Short fixed-format reports**: give every agent a JSON schema (done / not_done / commits /
   screenshots; findings / recommendations) and ask for terse telegraphic English.
4. **Partial reads**: Grep + Read with offset/limit; never read huge files whole (a 6000-line
   post-process shader, a renderer .cpp, game logs).
5. **Few parallel agents on the same topic**; parallelize only independent reading.

Rejected ideas: writing prompts in Chinese or "caveman" language saves almost nothing (similar token
counts) and lowers quality. Talk to the user in their language, shorter.

Put these rules in a `TERSE` constant appended to every agent prompt of a workflow.

## Workflow shape that works for a feature

```
Research  (2-3 agents in parallel, read-only, low/medium effort, schema output)
Implement (ONE agent: the files are shared, parallel writers conflict)
Verify    (a different agent, skeptical, tests in the real app with its own screenshots,
           re-checks that the other characters/features are unchanged, reads the diff)
Fix       (only if verify.ok is false: one round with the verifier's problems)
```

- Parallelism belongs in research; in code writing it only causes conflicts.
- Give the verifier the implementer's report but tell it not to trust it.
- Tell every agent which files another running agent/workflow owns ("don't touch X").

Rounds of polish over a backlog (find, fix, re-check):
- Keep a `pending` list and drop an item only when an implementer's report says `<id>: done` (or
  `wontfix`). A carry list that is reset after round 1 silently loses every item round 1 skipped.
- Big staged items (tech upgrades) never fit a polish implementer's time box, so they are skipped every
  round. Give them their own lane: a second implementer in its **own worktree/branch** with a longer
  box (~2.5 h, one milestone each), then a small merge agent at the end of the round.
- While the backlog is long, skip scouting for new items. The re-check hunt stays (short box, ~15 min),
  and its regressions join the backlog. Stop once the backlog is empty or two rounds make no progress.

## Resuming and changing a running workflow

- To change prompts mid-run: stop it, edit the script file, resume with `resumeFromRunId`.
  Finished agents replay from cache **only if their prompt and options are byte-identical** — so add
  new rules (e.g. TERSE) only to the prompts of agents that haven't finished, and leave finished ones
  untouched. Changing `effort` also breaks the cache.
- Check `journal.jsonl` in the run's transcript dir to see which agents finished.
- Resume with the **same `args`** as the first launch: the args feed the prompts, so different args
  re-run everything from round 1. Keep the launch args in a file so you can pass them back unchanged.
- To change only the later rounds, gate the new logic on the round number (`if (r >= 4)`). Then the
  prompts of the rounds already finished stay byte-identical and replay from the cache.
- Stopping a workflow can leave its agents' test games running: find them by exe path (the agent's
  scratchpad bin) and close them.

## Several workflows on one machine

- Budget the shared resource across all running workflows, not per workflow: game instances are
  RAM-bound (~2.8 GB each, 3 in all on a 32 GB laptop), so give each workflow a quota ("at most 2", "only
  1") and say in every prompt that another workflow runs beside it.
- Code-only workflows (release scripts, log tools) run in their own git worktree beside the
  game-testing ones: no builds, no goalc, no game in the main tree.
- Every test process gets an instance number whose ports never collide with the user's game; never let a
  test reach the default ports.
- When the user changes scope (e.g. "only Jak 3 for now"), stop, add one SCOPE line to the shared
  prompt, and relaunch. For workflows whose finished agents you want to keep, append the new rule only
  to the prompts of agents that haven't run yet (a suffix constant), so the cache still replays the
  finished ones.
- Keep the approved queue of workflows (order, scope, rejected ideas) in memory, so it survives
  a compacted context.

## Pausing everything for a priority

- Stop the workflows and agents, then close their leftover test processes. Match the processes by
  command line (their per-instance config path), never by name only: the user's game is a gk too.
- `git status`: stash a paused workflow's work in progress under a named stash
  (`git stash push -m "chars-wip: ..." -- <files>`), so the priority work starts from a clean tree.
- Tell the new agents never to pop or drop that stash. When the paused workflow resumes, tell it to
  pop the stash first.
- **Workflow agents of one session share its scratchpad directory**: a generic `scout.ps1`, `bin\`
  or `cfg\` written by one agent is overwritten by a parallel one mid-run (seen: an instance-17 agent
  rewrote an instance-18 agent's launcher between two calls). Name every scratch file and folder
  after the agent's instance or role (`scout18.ps1`, `bin18\`, `cfg18\`, `shots_<tag>\`).

## Stopping agents

- After stopping an agent, run `git status`: it may leave uncommitted debug edits (e.g. a shader
  writing debug colours that the game hot-reloads). Save them as a patch in the scratchpad
  (`git diff -- file > x.patch`) and restore the file, so the user's game isn't affected.
- If an agent can't reproduce a bug from the user's screenshot, look at the screenshot's conditions
  (weather, sky, time of day) before blaming the code — a "morning fog" bug wasn't visible in clear
  weather.

## Releases on a slow line (0.2-0.5 MB/s, 408 timeouts, DNS drops)

- Create the GitHub release as a **draft**, upload small assets first, then each big file with its
  own retry loop (`gh release upload --clobber`, 30 s wait, check the asset `state == "uploaded"` via
  `gh release view --json assets`); publish as soon as the main assets are up, the optional ones last.
- In PowerShell, quotes inside a `--jq` string are stripped: write `\"uploaded\"`.
- Publish dependent metadata (a launcher's mods.json pointing at an asset) only after that asset is up.
- Don't put `git push` at the end of an unattended upload script while agents are committing WIP:
  it would publish their unfinished commits.
- Keep editor-only/kit assets out of the shipped data folder (a separate gitignored dir the editor
  also searches); make the release script check that every asset the game's manifest names is in.

## Housekeeping

- Measure disk use with a small Python `os.scandir` walker (skip junctions) rather than Explorer.
- Moving files to the Recycle Bin (Microsoft.VisualBasic.FileIO, SendToRecycleBin) keeps deletions
  reversible; emptying the bin and changing system settings (page file, hibernation) are the user's.
- **Never pipe a script that cleans up into `Select-Object -First N`** (PowerShell): once N lines are out it stops the
  upstream script, so its `Stop-Process` at the end never runs; three test games stayed open and halved the
  next A/B's fps. Collect the output into a variable, then filter it.
