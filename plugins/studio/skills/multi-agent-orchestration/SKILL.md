---
name: multi-agent-orchestration
description: How to run sub-agents and dynamic workflows cheaply and safely on a big game project - token economy rules, the research/implement/verify/fix workflow shape, resuming a workflow without redoing finished agents, stopping agents without leaving debug edits behind, and slow-line release uploads. Use before spawning agents or writing a Workflow script, and when the user asks to save tokens.
---

# Orchestrating agents and workflows

Lessons from long sessions on Jak Enhanced (OpenGOAL fork: C++, GOAL, shaders, Blender, releases).

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

## Resuming and changing a running workflow

- To change prompts mid-run: stop it, edit the script file, resume with `resumeFromRunId`.
  Finished agents replay from cache **only if their prompt and options are byte-identical** — so add
  new rules (e.g. TERSE) only to the prompts of agents that haven't finished, and leave finished ones
  untouched. Changing `effort` also breaks the cache.
- Check `journal.jsonl` in the run's transcript dir to see which agents finished.

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
