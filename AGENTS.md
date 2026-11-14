# Agent rules for this repository

## The human merges. Always.

- **Never merge a pull request.** No `gh pr merge`, no auto-merge, no "merge when
  checks pass". Open the PR and stop.
- **Never push to `master`.** It is protected; treat a rejected push as the
  correct outcome, not an obstacle to work around. Do not disable branch
  protection to force a push.
- **Never force-push a shared branch.** `--force-with-lease` is still a
  force-push.

## Working shape

1. Branch from the current `origin/master`.
2. Commit there.
3. Push the branch, open a PR with a body that explains *why*.
4. Stop. The human reviews and merges.

## If a commit lands on `master` by accident

Move it, do not push it:

```bash
git branch fix/<name>          # keep the commit
git reset --hard origin/master # master back in sync
git checkout fix/<name>
git push -u origin fix/<name>
```

## Verify before every push

```bash
git branch --show-current      # must not be master
git status -sb                 # local and remote in sync
```

## How to work with the human

- **The human merges. The agent does not.** Open the PR, then stop.
- **Keep going until you are blocked.** Do every step you can do yourself; do not stop at a plan or a description when the work is doable.
- **End every turn with explicit next steps** for the human: what to merge, what to run, what to decide, in order.
- Prefer one PR per concern, branched from current `origin/master`, with a body that explains *why*.
