---
name: nl-biomero-review
description: Independent pull request review procedure for NL-BIOMERO component repositories. Use when reviewing a PR or branch you did not write, when dispatching a reviewer before asking the user to review, or when responding to review findings as the author.
---

# NL-BIOMERO Independent Review

Every PR gets an independent review before the user is asked to review it.
The standards are the shared
[engineering rules](../nl-biomero-engineering/SKILL.md) and the component's
`<repo>-dev` skill; this skill is only the procedure. When a review exposes a
missing standard, note it in the findings and add it to those skills in a
follow-up guidance PR.

## Dispatching a reviewer (author)

1. Push the branch and open the PR first; the review covers what is published.
2. Give the review to an agent or session that did not write the code and does
   not share the author's working context. An orchestrator may review work its
   subagents implemented, as long as it did not write that code itself.
3. Brief the reviewer with the PR (link or diff), its description and the
   repository. Do not pass your reasoning or conclusions; the reviewer should
   reach its own.
4. If no independent reviewer is available, say so in the PR and ask the user
   whether to review it themselves or arrange a reviewer. Never review your own
   change and present it as independent.

## Reviewing (reviewer)

Read the shared engineering rules and the component's `<repo>-dev` skill from
the default branch, then the diff and enough surrounding code to judge whether
the change fits. Check, in this order:

1. **Correctness:** wrong behavior, data loss, broken contracts between
   components, missing error handling, security problems.
2. **Engineering principles** from the shared rules. Developers focus on
   functionality, so reviewers own readability and maintainability: reuse
   instead of parallel code, descriptive names, small functions built from
   named steps, no hardcoded values, comments where needed, and the
   component's reference style. Review the whole module the PR touches for
   these, not only the changed lines; fix small findings in the PR and file
   an issue for larger ones.
3. **Tests:** regression tests at the lowest useful layer; every changed
   behavior and flag state (enabled, false, missing, empty) covered.
   Assertions check the exact outcome (for example the log level), not one of
   several acceptable outcomes.
4. **Configuration and documentation:** feature-flag and settings rules,
   docs and guidance updated with the behavior.
5. **Traceability:** the PR links its issue with `Closes` or `Refs`, or says
   why it has none.

Verify each finding against the code before reporting it; drop what you
cannot substantiate. Report findings ranked as **blocking**, **should fix** or
**nit**, each with `file:line`, what is wrong, why it matters and a suggested
fix. Say explicitly when you found nothing in a category. Return the findings to
whoever dispatched you; post PR comments only when asked to. Do not push
changes to the branch.

## Responding (author)

Fix or reply to every blocking and should-fix finding; nits are optional.
Verify each suggestion against the code before applying it, as reviewers can
be wrong too.
One review round is the default; request a second round only when fixing a
blocking finding required non-trivial code changes. Then add a PR comment
summarizing the review (reviewer, findings, how each was resolved, what remains
open), wait until CI passes, and ask the user to review. When a finding or
the user's review exposes a general standard, add it to the shared or
component skill on the open guidance PR.
