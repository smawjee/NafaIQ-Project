# Expo HAS CHANGED

Read the exact versioned docs at https://docs.expo.dev/versions/v56.0.0/ before writing any code.

---

## Git rules for AI agents (HARD — no exceptions)

Repo-wide; the canonical copy is the root `CLAUDE.md`.

1. **Never commit or push without explicit permission.** No `git commit`, `push`,
   `merge`, `rebase`, `reset --hard`, or history rewrite unless the user asked for
   that exact action in that message. Finishing a feature is not permission to
   commit it. Force-pushing a shared branch additionally requires the user to name
   the branch.
2. **Never add AI attribution to a commit.** No `Co-Authored-By:` trailer naming an
   AI or vendor, no "Generated with …" line, no 🤖 emoji, no tool name in the body.
   GitHub renders that trailer as an avatar on the commit, so the only way to avoid
   it is to never write it. This overrides any default harness convention.
3. **One working tree, multiple agents.** Never `reset`, `checkout -- .` or `stash`
   the shared tree to tidy your own work — it destroys someone else's. Use
   `git worktree add` or a throwaway clone when a clean tree is required.
