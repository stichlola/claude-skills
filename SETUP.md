# Setup: put the shared skills into the current project

For an agent asked to "open stichlola/claude-skills and do what the README says". Do every step without
asking, then report in the user's language. Running it again on a project that has them updates them.

1. **Get this repository.** If it is not already on disk, attach it to the session (in Claude Code cloud
   sessions: the `add_repo` tool with owner `stichlola`, repo `claude-skills`, read access) and clone it
   next to the project, e.g. `git clone --depth 1 https://github.com/stichlola/claude-skills
   /home/user/claude-skills`. If it is on disk, `git -C <path> pull` it.
2. **Find the project**: the repository the session is working on (its root, `git rev-parse --show-toplevel`),
   and the branch the session's instructions name (create it if missing; never commit to another).
3. **Copy the skills**: `<claude-skills>/tools/install-into.sh <project root>`. It replaces
   `.claude/skills/<skill>/` for each shared skill and leaves the project's other skills alone.
4. **Add one line to the project's `CLAUDE.md`** (create the file at the root if missing; skip if a line
   mentioning `stichlola/claude-skills` is already there), in the language the file is written in. Italian:

   ```markdown
   - **Skill condivise** in `.claude/skills/` (copiate da `stichlola/claude-skills`): Tripo, Blender (scavo e
     indossabili), prestazioni three.js, pipeline Unreal Engine, estrazione OpenGOAL (Jak), flusso di lavoro. Le scoperte utili anche ad altri progetti vanno aggiunte lì (poi si
     ricopiano qui con "apri stichlola/claude-skills e fai quanto scritto nel README").
   ```

   English:

   ```markdown
   - **Shared skills** in `.claude/skills/` (copied from `stichlola/claude-skills`): Tripo, Blender hollowing
     for wearables, three.js performance, Unreal Engine pipeline, OpenGOAL (Jak) extraction, agent workflow. Findings useful to other projects go there (then re-copy them here
     with "open stichlola/claude-skills and do what the README says").
   ```
5. **Commit and push**: `git add .claude/skills CLAUDE.md`, commit with the project's message conventions
   (e.g. "Shared agent skills from stichlola/claude-skills"), push the branch (retry on network errors).
   If the project's CLAUDE.md asks for more after a push (other branches kept in step, update commands for
   the user), do that too. If the project keeps a change log for agent edits (e.g. `AGENT_CHANGES.md`),
   add an entry.
6. **Report** in one short message: which skills were installed or updated, the commit, and that every
   new session of this project now has them (they load by themselves when a task needs them).
