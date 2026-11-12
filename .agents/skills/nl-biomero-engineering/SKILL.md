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

Reviewers check every pull request against these principles. Readable code
is what makes review possible: when functions, variables and grouping say what
the code does, a reviewer can see the approach and disagree with it. Code that
has to be traced value by value hides its design from review, so readability
is a requirement, not polish.

- Keep it simple. Prefer the smallest change that solves the problem; do not
  add layers, frameworks, options or abstractions for hypothetical needs.
- Size safeguards to the real threat. Do not add checks against actors who
  already have equal or greater access (for example, whoever can submit
  import orders can already import any data); state the trust assumption in
  the docs instead.
- Reuse before adding (DRY). Extend the component's existing modules, helpers
  and patterns instead of building a parallel implementation; add an optional
  parameter to an existing function rather than a second code path that must
  be maintained separately. Generic operations (submitting a scheduler job,
  running a remote command, looking up workflow tasks) live once, in the main
  or helper classes, so every feature uses the same site configuration and
  future features reuse them. Put behavior in the
  component that owns it (see each component's ownership section) and keep
  workflow decisions in the callers rather than in shared libraries.
- Match the surrounding code: its naming, structure, error handling, logging
  and test style. New code should look like it was written by the same team.
  A new module follows the package's established modules, not only its own
  file: the same docstring format, type hints, naming and quoting. Each
  component's `<repo>-dev` skill names its reference module.
- State behavior changes. A PR described as logging-only, refactoring or
  style must not change behavior; list any deliberate change in the
  description.
- Keep functions focused and readable. Split long functions with many exits
  or mixed responsibilities. A function should read as a short sequence of
  well-named steps and decisions, with each step extracted into a named
  sub-function.
- Name things by what they are or do. Functions say what they do
  (`sha256_of_json`, not `_canonical_digest`; not `run`, `_batch` or
  `_check`), and the variable holding a result says what it means
  (`canonical_digest = sha256_of_json(...)`). Name conditions and items that
  drive decisions (`shallower_already_completed`, `existing_task`) instead of
  reusing `matches[0]`; store a repeated expression once in a named variable.
  Give non-trivial commands and queries a named variable before running them.
- Do not hardcode values that may change, such as versions, contract numbers,
  paths, names and limits. Define them as constants at the top of the module
  or class (shared constants in the component's constants module) and expose
  them as function parameters that default to those constants, so they can be
  changed without editing function internals. Add such a parameter only where
  it is passed down from the public entry point; a parameter no caller can
  reach is dead code.
- Comment what a reader cannot infer: why a branch exists, and what an
  unfamiliar tool or system call does (for example `flock`) and whether its
  availability is checked at setup.
- Prefer f-strings for string formatting, including log messages; use other
  forms only where an f-string does not work.
- Log every decision. Each branch that chooses a path (enabled or disabled,
  reuse or fresh, keep or remove, retry or fail, local or remote) logs what it
  decided and why, at least at DEBUG; actions that change or delete data, or
  run remote work, log at INFO. Errors are logged with context, never silently
  swallowed. Someone reading the logs must be able to tell what happened.
  A feature that is simply switched off is the normal path: log that skip at
  DEBUG, and use WARNING when a feature is enabled but cannot run, so results
  silently fall back. Either log an error or raise it with its context, not
  both; the code that handles the exception logs it once, with its traceback.
- Prefer typed structures over free-form dicts and string keys for state
  that crosses functions or components.
- Give every setting one source, one reader and one parser. Other code and
  components receive the parsed value instead of reading the environment or
  INI again; values that must match across components come from that single
  source.
- Backward compatibility means supported deployments keep working; it does
  not mean every new feature must support older execution paths. Where a
  feature's prerequisites are missing (for example, Zarr result handling needs
  the importer together with BIOMERO core), leave the feature disabled and log
  why, instead of retrofitting it into those paths.
- New features are off in code and on in the NL-BIOMERO demo. A missing,
  empty or false flag leaves a feature disabled, because existing servers
  upgrade components without adding new flags. The NL-BIOMERO `.env` and
  `.env.shared` are the flagship demo for clean installs and the setup we test
  on: they enable every feature, and everything must work there. Do not report
  an enabled flag in the demo as a missing opt-in; check the code default
  instead. See `omero-biomero-expert` for the flag rules.
- Documentation is part of a feature. When a feature is disabled for a
  release, withdrawn or removed, hide or remove its documentation pages and
  navigation (Sphinx, MkDocs, READMEs, UI help) in the same change, so the docs
  describe only what users can use.

## Issues and the project board

Planned work is tracked on the
[BIOMERO Roadmap board](https://github.com/orgs/NL-BioImaging/projects/2).
The board is private but repository issues are public: write issues for a
public audience and keep non-public details out of them.

- Start work from an issue, in the repository whose code changes. If agreed
  work has no issue yet, create one, add it to the board and tell the user.
  Keep issues at the same granularity as PRs: one issue per functionality per
  repository, listing its parts, rather than one issue per sub-change.
  For work across repositories, create a parent issue in NL-BIOMERO with one
  sub-issue per repository, and close the parent when its last sub-issue
  closes. NL-BIOMERO issues and sub-issues are added to the board
  automatically; add any other issue yourself:
  `gh project item-add 2 --owner NL-BioImaging --url <issue-url>`.
- When a repository gets its first issue on the board, link it to the board
  (`gh project link 2 --owner NL-BioImaging --repo NL-BioImaging/<repo>`).
  Linking only associates the repository; it does not add issues.
- The board sets Status when items are added, when a PR is linked and when
  items are closed or merged. Set In Progress yourself only when you start
  before a PR exists, and set Blocked with a comment explaining why.
  Priority, Impact and Effort are the user's decisions; suggest values in a
  comment, do not set them.
- Every PR description either links its issues or says why it has none (for
  example a guidance-only or trivial chore PR). Write
  `Closes NL-BioImaging/<repo>#<n>` for each issue the PR completes; GitHub
  closes it when the PR merges into the default branch. Write
  `Refs NL-BioImaging/<repo>#<n>` for partial work; this mentions the issue
  without linking or closing it.

## Development branches and pull requests

Work on a dedicated branch and publish it: commit and push work in progress
rather than leaving it uncommitted or only local, so it is visible and
recoverable. This applies to all component repositories and NL-BIOMERO's
submodules, including hotfixes and guidance changes.

- Open pull requests ready for review by default; use draft status only when
  the user asks. Record dependencies and merge order in the PR description,
  with a clear description of the final change and its validation. Do not hold
  work back in a draft PR or local branch; the independent review below runs
  on the ready PR.
- Keep one PR per scope, where the scope is one piece of functionality in one
  repository. Logging, readability fixes, reuse refactors and tests for that
  functionality belong in the same PR, and one PR may close several issues
  about it. Add further changes with the same scope to the open PR instead of
  opening a stacked or follow-up PR; split only for a separate functionality
  or a required merge order across repositories.
- During a review or other longer piece of work, collect guidance changes on
  one open guidance PR per repository and merge it when that work is done.
  Keep guidance PRs separate from PRs that change code or configuration.
- Make focused, coherent commits and push them as you go. Run cheap, relevant
  checks before pushing and let the required CI checks be the full-suite gate.
  If CI fails, inspect it and push a follow-up fix. Local runs can skip
  platform-specific tests, so a PR is ready for the user only when CI passes
  on every platform it runs. Use proportionate local
  verification before a release, a direct default-branch push or a change
  without suitable CI coverage.
- Preserve unrelated working-tree changes and never use destructive Git
  commands (`reset --hard`, `clean`, force-push, branch deletion of unmerged
  work) unless the user asks.
- Before asking the user to review, have the open PR reviewed independently
  following the [independent review procedure](../nl-biomero-review/SKILL.md),
  address the findings, and summarize the outcome in the PR. Any capable agent
  that did not write the change can be the reviewer.
- The user's unconditional "approved" or "accepted" of a specific PR (in
  conversation or as a PR comment) authorizes only the squash-merge of that PR:
  merge it once the checks pass, respecting any recorded merge order, then
  delete its remote and local branch. If the approval is conditional or it is
  unclear which PR it covers, ask. Agent PRs are opened with the user's
  credential, so GitHub does not let the user approve them formally; do not
  wait for a GitHub approval. Tags, GitHub releases or prereleases, stack
  restarts and deployments still need their own explicit authorization (see
  the prerelease rules in `omero-biomero-expert`). Do not push directly to
  `main`/`master` unless the user explicitly asks.
- Before creating a PR, verify the intended repository, head branch and base
  branch; local clones may also reference upstream forks. If the GitHub CLI is
  unavailable, use the REST API with the configured Git credential, keeping it
  in memory and never printing or writing it.
- Otherwise this workflow does not authorize publication, merging, releases,
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
stash, reset, clean or delete in them; the only exception is switching branch
for a local deployment, below.

- Deployment repositories (such as `deploy-omero`, site forks of NL-BIOMERO and
  the local Slurm clusters) are also the user's: keep them and their deployment
  branches, and follow the operations skills in those repositories.
- A local stack deployment uses the primary NL-BIOMERO checkout with
  `docker-compose.yml`, which builds the images with the pinned component
  versions, and NL-BIOMERO-Local-Slurm or NL-BIOMERO-Local-Slurm-GPU. Use
  `docker-compose-dev.yml` only when actively developing the OMERO.biomero
  frontend: it mounts the OMERO.biomero checkout cloned next to NL-BIOMERO (see
  the OMERO.biomero README) so changes show without rebuilding images. When the user
  asks to verify a release or PR branch locally, confirm the checkouts are clean, then switch them to that pushed
  branch; never commit, stash, reset or clean there. Report which branches they
  are on, and switch them back to the default branch when the deployment is
  finished or the user says so.

- Do agent work in a dedicated checkout created for the task: a `git worktree`
  of the primary checkout or a separate clone, in a temporary or clearly
  agent-owned location, named `<repo>-<topic>`. Record where you created it.
- Put scratch output (logs, fixtures, measurements, generated files) outside
  the repositories, next to that checkout or in a temporary directory. Give
  virtual environments and scratch directories names of your own; never
  reuse or delete a directory another agent or the user created.
- Once the work is pushed and its pull request is open, remove what you
  created: `git worktree remove <path>` then `git worktree prune`, delete the
  local branch, and delete temporary clones and scratch output. Review
  follow-ups get a fresh checkout of the pushed branch.
- Before removing anything, confirm there is no uncommitted or unpushed work
  (`git status`, `git log @{u}..`, stashes, branches without an upstream). If
  there is, push it or keep the checkout and report it; never delete it.
- End the task by reporting which checkouts were removed and which remain, and
  why.
