---
name: nl-biomero-engineering
description: Shared engineering rules for every NL-BIOMERO component repository (NL-BIOMERO, biomero, biomero-scripts, BIOMERO.importer, OMERO.biomero, BIOMERO.shallower, biomero-schema, BIOMERO.ZarrViewer). Use before any design, implementation or review work in these repositories, when opening or reviewing pull requests, when writing or changing agent guidance, and when finishing work that created local checkouts.
---

# NL-BIOMERO Engineering

These rules apply to all NL-BIOMERO component repositories. Each component's
own `<repo>-dev` skill adds component-specific rules; if the two conflict, the
component skill must say why. Do not copy these rules into component skills;
link to this file instead:
<https://github.com/NL-BioImaging/NL-BIOMERO/blob/master/.agents/skills/nl-biomero-engineering/SKILL.md>

## Engineering principles

Reviewers check every pull request against these principles.

- Keep it simple. Prefer the smallest change that solves the problem; do not
  add layers, frameworks, options or abstractions for hypothetical needs.
- Reuse before adding. Extend the component's existing modules, helpers and
  patterns instead of building a parallel implementation.
- Match the surrounding code: its naming, structure, error handling, logging
  and test style. New code should look like it was written by the same team.
- Keep functions focused and readable. Split long functions with many exits
  or mixed responsibilities.
- Log every decision. Each branch that chooses a path (enabled or disabled,
  reuse or fresh, keep or remove, retry or fail, local or remote) logs what it
  decided and why, at least at DEBUG; actions that change or delete data, or
  run remote work, log at INFO. Errors are logged with context, never silently
  swallowed. Someone reading the logs must be able to tell what happened.
- Prefer typed structures over free-form dicts and string keys for state
  that crosses functions or components.

## Development branches and pull requests

Work on a dedicated branch and publish it: commit and push work in progress
rather than leaving it uncommitted or only local, so it is visible and
recoverable. This applies to all component repositories and NL-BIOMERO's
submodules, including hotfixes and guidance changes.

- Open pull requests ready for review by default; use draft status only when
  the user asks. Record dependencies and merge order in the PR description,
  with a clear description of the final change and its validation. Do not add
  a separate draft or pre-PR stage.
- Make focused, coherent commits and push them as you go. Run cheap, relevant
  checks before pushing and let the required CI checks be the full-suite gate.
  If CI fails, inspect it and push a follow-up fix.
- Before asking the user to review, have the open PR reviewed independently
  following the [independent review procedure](../nl-biomero-review/SKILL.md),
  address the findings, and summarize the outcome in the PR. Any capable agent
  that did not write the change can be the reviewer.
- Merge only when the user authorizes it, through the PR after the checks pass.
  Prefer squash merging so each PR is one revertible commit. Do not push
  directly to `main`/`master` unless the user explicitly asks.
- Before creating a PR, verify the intended repository, head branch and base
  branch; local clones may also reference upstream forks. If the GitHub CLI is
  unavailable, use the REST API with the configured Git credential, keeping it
  in memory and never printing or writing it.
- This workflow does not authorize unrelated publication, merging, releases,
  deployment or destructive actions.

## Agent guidance

Guidance must work for any agent or tool, from any provider.

- Every repository has a root `AGENTS.md`: a short entry point stating what the
  repository is, how to build and test it, its boundaries with other
  components, and which skills to read. Keep it under about 60 lines.
- Rules live in `.agents/skills/<name>/SKILL.md` and the `references/*.md`
  files it routes to. Each component has one `<repo>-dev` skill with the same
  shape: ownership and boundaries, configuration, testing, documentation,
  release notes.
- Tool-specific files only point to the shared guidance and never contain
  rules, so every tool discovers the same content natively:
  - `CLAUDE.md` contains just `@AGENTS.md`.
  - `.claude/skills/<name>/SKILL.md` is a discovery stub per skill: the same
    frontmatter as `.agents/skills/<name>/SKILL.md` and a body that only
    links to it. Update the stub's frontmatter whenever the source changes.
    Do not use symlinks; Windows checkouts turn them into plain files.
  - Tool metadata such as `agents/openai.yaml` may describe a skill but must
    not add rules.
- Write rules as imperatives with a one-line reason. Do not name a specific
  agent, model or tool in a rule; say "run the tests", not which tool runs them.
- Keep durable rules separate from status. Do not put version pins, release
  progress, incident history or acceptance results in skills; those belong in
  `plans/`, pull requests, release notes or package metadata.
- Do not include machine-specific paths, usernames, hostnames or secrets. Use
  paths relative to the repository or `<placeholder>` names.
- Keep a `SKILL.md` to about 200 lines and route detail to `references/`.
- The guidance on the default branch is authoritative. When working on an
  older branch or checkout, compare its guidance with the default branch
  before design or review work and follow the newer rules.
- Change guidance through a pull request like code. Guidance-only changes do
  not need a package release.

## Local checkouts

The user's primary checkouts belong to the user: one per repository on its
default branch, with BIOMERO.importer as NL-BIOMERO's `biomero-importer`
submodule. Read from them freely, but do not switch their branch, commit,
stash, reset, clean or delete in them.

- Do agent work in a dedicated checkout created for the task: a `git worktree`
  of the primary checkout or a separate clone, in a temporary or clearly
  agent-owned location, named `<repo>-<topic>`. Record where you created it.
- Put scratch output (logs, fixtures, measurements, generated files) outside
  the repositories, next to that checkout or in a temporary directory.
- Once the work is pushed and its pull request is open, remove what you
  created: `git worktree remove <path>` then `git worktree prune`, delete the
  local branch, and delete temporary clones and scratch output. Review
  follow-ups get a fresh checkout of the pushed branch.
- Before removing anything, confirm there is no uncommitted or unpushed work
  (`git status`, `git log @{u}..`, stashes, branches without an upstream). If
  there is, push it or keep the checkout and report it; never delete it.
- End the task by reporting which checkouts were removed and which remain, and
  why.
