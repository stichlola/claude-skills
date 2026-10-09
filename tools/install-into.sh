#!/usr/bin/env bash
# Copy (or refresh) the shared skills into a project, as project skills: .claude/skills/<skill>/.
# Cloud sessions load a repository's own .claude/skills, so this is what makes the skills work there.
#   tools/install-into.sh /path/to/project
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
dest="${1:?usage: tools/install-into.sh /path/to/project}"
mkdir -p "$dest/.claude/skills"
for skill in "$here"/plugins/studio/skills/*/; do
  name="$(basename "$skill")"
  rm -rf "$dest/.claude/skills/$name"
  cp -R "$skill" "$dest/.claude/skills/$name"
  echo "installed $name"
done
