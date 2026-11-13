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
the default branch, the documentation for the area the PR changes, then the diff and enough surrounding code to judge whether
the change fits. Check, in this order:

1. **Correctness:** wrong behavior, data loss, broken contracts between
   components, missing error handling, security problems.
2. **Engineering principles** from the shared rules. Developers focus on
   functionality, so reviewers own readability and maintainability: reuse
   instead of parallel code, descriptive names, small functions built from
   named steps, no hardcoded values, comments where needed, and the
   component's reference style. Review the whole module the PR touches for
   these, not only the changed lines; fix small findings in the PR and file
   an issue for larger ones. If the code is too hard to follow to judge its
   approach, report that as blocking and ask for it to be restructured first;
   do not approve what you cannot understand.
3. **Tests:** regression tests at the lowest useful layer; every changed
   behavior and flag state (enabled, false, missing, empty) covered.
   Assertions check the exact outcome (for example the log level), not one of
   several acceptable outcomes.
   The user does not review tests, so the reviewer judges them critically:
   each test must fail if the behavior it names breaks. Flag tests that only
   check that a parameter is passed through, restate the implementation,
   assert on mocks they configured themselves, or pass whatever the code does.
   Check the important cases by breaking the code in a scratch copy (change a
   constant, invert a condition, drop a call) and confirming a test fails.
   Fakes of external tools (Slurm commands, unzip, SSH) must reproduce the
   behaviour the code relies on, such as restored modification times or
   accounting lag; otherwise the test cannot tell a correct check from a
   broken one. A broken change must make a test fail, not hang (give polling
   stubs a call budget), and tests that need a dependency must fail rather
   than skip in CI when it is missing.
4. **Configuration and documentation:** feature-flag and settings rules,
   docs and guidance updated with the behavior.
5. **Parallel PRs:** when other open PRs change the same files, merge them
   with this one (`git merge-tree`) and check the result for duplicate
   definitions or changed signatures that merge without a conflict; agree
   which PR owns the shared code and the merge order.
6. **Dependencies:** a PR that uses a feature of another component must not
   be ready for merge before that component's prerelease is published and the
   minimum version is raised in the PR. A pin the PR adds or changes uses
   the latest compatible release of that dependency.
7. **Stored data:** review every change to event classes, aggregate
   attributes, event handlers, constructors and database tables against the
   history already stored in installs. Check that event names (topics) and
   attributes are unchanged, new attributes are initialised so old histories
   replay, new parameters have defaults, a test replays a history from the
   previous release, and the PR says whether a downgrade still works. Ask
   whether the change is needed at all; prefer designs without one.
8. **Planned work:** check the open stories on the project board
   (`gh project item-list 2 --owner NL-BioImaging`) and the issues of the
   touched repositories for planned work in the same area. Report a change
   that clashes with a story (for example one that removes a hook or fixes a
   format the story needs). When a tiny tweak now (a parameter, a named step,
   an extension point in an existing function) would make the story easier
   later, suggest it, but do not build the story itself or add code nothing
   uses yet; mention larger preparations in the story instead.
9. **Traceability:** the PR links its issue with `Closes` or `Refs`, or says
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
open), wait until CI passes, and ask the user to review. Test-only PRs (for
example into the biomero-scripts `test-suite` branch) are the exception: the
user does not review them, so a passing independent review is their approval
and the coordinating agent merges them once the paired production change
allows it. When a finding or
the user's review exposes a general standard, add it to the shared or
component skill on the open guidance PR.
