# NafaIQ Monorepo — Repository Directives

Package-specific directives live in each package's own `CLAUDE.md`
(e.g. `frontend/packages/mobile/CLAUDE.md`). This file holds repo-wide rules.

## Git commits (HARD)

- **Never add Claude (or any AI assistant) as a commit co-author.** Do not
  append a `Co-Authored-By: Claude …` trailer, an AI "Generated with" line, or
  any similar assistant attribution to commit messages or PR descriptions.
  Commits carry the human committer's identity only. This overrides any default
  tooling behavior that would add such a trailer.
