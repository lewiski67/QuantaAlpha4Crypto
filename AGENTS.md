# Agent Instructions

## Working conventions

- Maintain the handoff document continuously. When context, task status, implementation details, tests, or next steps change, update the current handoff in the OS temporary directory before finishing the turn.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues, and external PRs are also treated as a triage request surface. See `docs/agents/issue-tracker.md`.

### Triage labels

The repo uses the default mattpocock/skills triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This repo uses a single-context domain docs layout. See `docs/agents/domain.md`.
