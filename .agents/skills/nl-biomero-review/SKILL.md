---
name: nl-biomero-review
description: Independent pull request review procedure for NL-BIOMERO component repositories. Use when reviewing a PR or branch you did not write, when dispatching a reviewer before asking the user to review, or when responding to review findings as the author.
---

# NL-BIOMERO Independent Review

Every PR gets an independent review before the user is asked to review it.
The standards are the shared
[engineering rules](../nl-biomero-engineering/SKILL.md) and the component's
`<repo>-dev` skill; this skill is only the procedure. Do not keep a separate
checklist here: when a review exposes a missing standard, propose adding it to
those skills.

## Dispatching a reviewer (author)

1. Push the branch and open the PR first; the review covers what is published.
2. Give the review to an agent or session that did not write the change. An
   orchestrator may review its subagents' work; the author never reviews itself.
3. Brief the reviewer with the PR (link or diff), its description and the
   repository. Do not pass your reasoning or conclusions; the reviewer should
   reach its own.

## Reviewing (reviewer)

Read the shared engineering rules and the component's `<repo>-dev` skill from
the default branch, then the diff and enough surrounding code to judge whether
the change fits. Check, in this order:

1. **Correctness:** wrong behavior, data loss, broken contracts between
   components, missing error handling, security problems.
2. **Engineering principles:** simplicity, reuse of existing code, matching
   style, focused functions, decisions logged, typed state, errors not
   swallowed.
3. **Tests:** regression tests at the lowest useful layer; every changed
   behavior and flag state (enabled, false, missing, empty) covered.
4. **Configuration and documentation:** feature-flag and settings rules,
   docs and guidance updated with the behavior.

Verify each finding against the code before reporting it; drop what you
cannot substantiate. Report findings ranked as **blocking**, **should fix** or
**nit**, each with `file:line`, what is wrong, why it matters and a suggested
fix. Say explicitly when you found nothing in a category. Report findings to the
author (or as PR review comments); do not push changes to the branch yourself.

## Responding (author)

Fix or reply to every blocking and should-fix finding; nits are optional.
Push the fixes and request a re-review when the changes are substantial. Then
add a short summary to the PR (reviewer, findings, how each was resolved, what
remains open) and ask the user to review.
