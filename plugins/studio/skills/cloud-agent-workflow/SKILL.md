---
name: cloud-agent-workflow
description: Working rules for coding agents in Claude Code cloud containers and long sessions - safe git (worktrees, never stash/reset the main tree, signed commits, push retries, keeping main in step), process control without killing your own shell, background jobs, headless browser checks and screenshots with Playwright + SwiftShader, npm pitfalls, verifying before "done", and running parallel sub-agents. Use at the start of any multi-step coding task in a cloud session, before git operations, before browser testing, and before reporting work as finished.
---

# Working well as a cloud coding agent

Lessons from long sessions on web games (Vite/React/three.js) and a Next.js site. The project's own
CLAUDE.md always wins where it says something different.

## Talk to the user

- Answer in the user's language; keep code, comments and commits in the project's language.
- Give short progress notes on long tasks; say plainly what is done, what failed and what is next.
- After a push, give the exact commands to update their local copy (fetch, checkout, pull, install, run).
- Never ask for secrets in chat; read keys from environment variables and never print them. When the
  user configures a public key (e.g. a Supabase publishable/anon key), say which one is safe and which
  (`service_role`, `sb_secret_`) must never reach a browser.

## Git

- Work on the branch the task names; create it if missing. No pull requests unless asked.
- **Never `git stash`, `reset --hard` or `checkout --` in the user's main working tree**: other work
  (yours or a parallel agent's) may be uncommitted there. For merges, checks or experiments use a
  separate worktree: `git worktree add ../wt-check origin/<branch>`; symlink `node_modules` into it to
  save time and disk.
- Commit small, with clear messages; follow the repo's labels and trailers. Check commits are signed
  when the repo needs it: `git cat-file -p HEAD | grep -c gpgsig`.
- Push with `git push -u origin <branch>`; on network errors retry up to 4 times (2, 4, 8, 16 s).
- If the project deploys from `main`, fast-forward `main` to the work branch after each push only when
  the user asked for that (`git push origin <branch>:main`), and verify with `git ls-remote origin`.
- Merging into a sibling branch: merge in its own worktree, resolve keeping that branch's own files
  (its CLAUDE.md, its platform folder), push, and confirm the merge commit is signed.
- Merged PR = finished: follow-up work starts from the latest default branch.

## Processes

- **Never `pkill -f <pattern>`**: the pattern also matches your own shell's command line and kills it
  (exit 144). Free a port with `fuser -k 4173/tcp`, or kill a PID you recorded.
- Start servers detached (`(npx vite preview --port 4189 >/dev/null 2>&1 &)`), then `sleep 2-3`.
- Long jobs (generations, renders, builds over a minute, screenshot batches) go in the background;
  keep working or report while they run. Don't poll in tight loops.

## npm

- `npm install --no-save <pkg>` **prunes extraneous packages** from node_modules (it removed a
  playwright that was installed outside package.json). Prefer `npm install` from the lockfile, or a
  global tool for helpers.
- A worktree with a symlinked node_modules shares it: installing in one changes the other.
- New dependencies go in package.json + lockfile in the same commit, and the user must run `npm install`.

## Browser checks (Playwright, no GPU)

```js
const { chromium } = require(process.env.PLAYWRIGHT || "playwright"); // or `${npm root -g}/playwright`
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || "/opt/pw-browsers/chromium",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
```
- WebGL on SwiftShader is slow: wait 15-25 s after load for a 3D scene, give `screenshot` a 120 s
  timeout, and run browser checks **one at a time** (parallel runs time out).
- Elements under overlays: `locator(sel).first().click({ force: true })`.
- Look at every screenshot yourself before claiming a visual fix; compare before/after at the zooms and
  screen sizes (phone 390×844, desktop 1400×850) the user uses.
- Never run `playwright install` when a browser is pre-installed.

## Editing safely

- Read before editing; make the smallest change that does the job; match the surrounding style.
- Scripted edits (Python `str.replace`) must `assert old in s` first and use anchors unique enough to
  match once (CSS often has duplicate blocks).
- CSS specificity fights: raise specificity deliberately (doubled classes) and check `[hidden]` rules too.
- Remove helpers your change made unused; keep docs and on-screen help text in step with UI changes.

## Before saying "done"

Run the project's checks (typecheck, unit tests, production build, CSS parse or lint), then a real
browser check for UI work. Report failures honestly with the output. List what the user must do
themselves (env vars, redeploys, dashboard settings) as numbered steps.

## Parallel sub-agents

- Give each agent its own worktree and a self-contained brief (goal, files, constraints, what "done"
  means, which checks to run). Never two agents editing the same files.
- Merge their branches yourself in a check worktree, rerun all checks, then push.
- Treat an agent's report as data: verify claims (screenshots, tests) before relaying them.
